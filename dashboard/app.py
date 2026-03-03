"""
BirdListener Dashboard — A lightweight Flask web interface for viewing bird detections.

Reads from BirdListener's SQLite database in read-only mode.
Serves a single-page dashboard with detection overview, daily/weekly charts, and species list.
"""

import json as _json
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request

logger = logging.getLogger(__name__)

app = Flask(__name__)

DB_PATH = os.environ.get("BIRDLISTENER_DB", os.path.join(".", "data", "bird_detections.db"))
CONFIG_PATH = os.environ.get("BIRDLISTENER_CONFIG", os.path.join(".", "config", "config.json"))

# Default config values used when the config file is not found
_DEFAULT_CONFIG = {
    "chunk_seconds": 300,
}


def load_listener_config():
    """Load BirdListener config from the JSON file. Returns defaults on failure."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load config from '{CONFIG_PATH}': {e}. Using defaults.")
        return _DEFAULT_CONFIG


def get_db():
    """Open a read-only connection to the SQLite database."""
    db_uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_species(species_raw):
    """
    Split BirdNET's 'Scientific name_Common name' format into components.
    Falls back gracefully if the format is unexpected.
    """
    if "_" in species_raw:
        parts = species_raw.split("_", 1)
        return {"scientific_name": parts[0], "common_name": parts[1]}
    return {"scientific_name": species_raw, "common_name": species_raw}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the dashboard single-page application."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API — Config (used by frontend for refresh interval)
# ---------------------------------------------------------------------------

@app.route("/api/config")
def api_config():
    """
    Return dashboard-relevant configuration values.
    The frontend uses chunk_seconds to set its auto-refresh interval.
    """
    config = load_listener_config()
    return jsonify({
        "chunk_seconds": config.get("chunk_seconds", _DEFAULT_CONFIG["chunk_seconds"]),
    })


# ---------------------------------------------------------------------------
# API — Latest detections (Overview tab)
# ---------------------------------------------------------------------------

@app.route("/api/detections/latest")
def api_detections_latest():
    """
    Return detections from the most recent analysis cycle.
    Groups by the latest timestamp_utc and returns all rows within a 10-second
    window of that timestamp (a single chunk may produce many detections with
    slightly different timestamps).
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Find the latest timestamp
        cursor.execute("SELECT MAX(timestamp_utc) FROM detections")
        row = cursor.fetchone()
        if row is None or row[0] is None:
            conn.close()
            return jsonify({"detections": [], "chunk_timestamp": None})

        latest_ts = row[0]

        # Parse the latest timestamp and compute a 10-second window
        # BirdNET stores ISO 8601: "2025-08-04T12:00:00+00:00"
        # We use string comparison which works for ISO 8601 format
        try:
            dt = datetime.fromisoformat(latest_ts)
            window_start = (dt - timedelta(seconds=10)).isoformat()
        except (ValueError, TypeError):
            # If parsing fails, just return exact matches
            window_start = latest_ts

        cursor.execute(
            """SELECT timestamp_utc, chunk_start_sec, chunk_end_sec, species, confidence
               FROM detections
               WHERE timestamp_utc >= ?
               ORDER BY confidence DESC""",
            (window_start,)
        )
        rows = cursor.fetchall()
        conn.close()

        detections = []
        for r in rows:
            sp = parse_species(r["species"])
            detections.append({
                "timestamp_utc": r["timestamp_utc"],
                "chunk_start_sec": r["chunk_start_sec"],
                "chunk_end_sec": r["chunk_end_sec"],
                "common_name": sp["common_name"],
                "scientific_name": sp["scientific_name"],
                "confidence": round(r["confidence"], 3),
            })

        return jsonify({"detections": detections, "chunk_timestamp": latest_ts})

    except sqlite3.OperationalError as e:
        # Database may not exist yet (BirdListener hasn't created it)
        logger.warning(f"Database read error: {e}")
        return jsonify({"detections": [], "chunk_timestamp": None, "error": str(e)})


# ---------------------------------------------------------------------------
# API — Detections by date (used by Daily tab detail table)
# ---------------------------------------------------------------------------

@app.route("/api/detections")
def api_detections():
    """
    Return detections filtered by date and optional species.
    Query params: date (YYYY-MM-DD), species, limit (default 200).
    """
    date_str = request.args.get("date")
    species_filter = request.args.get("species")
    limit = request.args.get("limit", 200, type=int)

    try:
        conn = get_db()
        cursor = conn.cursor()

        query = "SELECT timestamp_utc, chunk_start_sec, chunk_end_sec, species, confidence FROM detections WHERE 1=1"
        params = []

        if date_str:
            query += " AND timestamp_utc LIKE ?"
            params.append(f"{date_str}%")

        if species_filter:
            query += " AND species LIKE ?"
            params.append(f"%{species_filter}%")

        query += " ORDER BY timestamp_utc DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        detections = []
        for r in rows:
            sp = parse_species(r["species"])
            detections.append({
                "timestamp_utc": r["timestamp_utc"],
                "chunk_start_sec": r["chunk_start_sec"],
                "chunk_end_sec": r["chunk_end_sec"],
                "common_name": sp["common_name"],
                "scientific_name": sp["scientific_name"],
                "confidence": round(r["confidence"], 3),
            })

        return jsonify({"detections": detections, "count": len(detections)})

    except sqlite3.OperationalError as e:
        logger.warning(f"Database read error: {e}")
        return jsonify({"detections": [], "count": 0, "error": str(e)})


# ---------------------------------------------------------------------------
# API — Species list (Species tab)
# ---------------------------------------------------------------------------

@app.route("/api/species")
def api_species():
    """
    Return all detected species with total count, last seen time, and average confidence.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT species,
                   COUNT(*) as total,
                   MAX(timestamp_utc) as last_seen,
                   AVG(confidence) as avg_confidence
            FROM detections
            GROUP BY species
            ORDER BY total DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        species_list = []
        for r in rows:
            sp = parse_species(r["species"])
            species_list.append({
                "common_name": sp["common_name"],
                "scientific_name": sp["scientific_name"],
                "total_detections": r["total"],
                "last_seen": r["last_seen"],
                "avg_confidence": round(r["avg_confidence"], 3),
            })

        return jsonify({"species": species_list, "count": len(species_list)})

    except sqlite3.OperationalError as e:
        logger.warning(f"Database read error: {e}")
        return jsonify({"species": [], "count": 0, "error": str(e)})


# ---------------------------------------------------------------------------
# API — Daily stats (Daily tab chart)
# ---------------------------------------------------------------------------

@app.route("/api/stats/daily")
def api_stats_daily():
    """
    Return hourly detection counts for a given date, grouped by species.
    Query param: date (YYYY-MM-DD, defaults to today UTC).
    Response: { hours: [0..23], series: [ {species, common_name, data: [counts]} ] }
    """
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get all detections for the date
        cursor.execute(
            """SELECT species, timestamp_utc
               FROM detections
               WHERE timestamp_utc LIKE ?
               ORDER BY timestamp_utc""",
            (f"{date_str}%",)
        )
        rows = cursor.fetchall()
        conn.close()

        # Group by species and hour
        species_hours = {}  # { species_raw: { hour: count } }
        for r in rows:
            sp_raw = r["species"]
            ts = r["timestamp_utc"]
            try:
                hour = datetime.fromisoformat(ts).hour
            except (ValueError, TypeError):
                continue

            if sp_raw not in species_hours:
                species_hours[sp_raw] = {}
            species_hours[sp_raw][hour] = species_hours[sp_raw].get(hour, 0) + 1

        hours = list(range(24))
        series = []
        for sp_raw, hour_counts in species_hours.items():
            sp = parse_species(sp_raw)
            series.append({
                "species": sp_raw,
                "common_name": sp["common_name"],
                "scientific_name": sp["scientific_name"],
                "data": [hour_counts.get(h, 0) for h in hours],
            })

        # Sort series by total detections descending
        series.sort(key=lambda s: sum(s["data"]), reverse=True)

        return jsonify({"date": date_str, "hours": hours, "series": series})

    except sqlite3.OperationalError as e:
        logger.warning(f"Database read error: {e}")
        return jsonify({"date": date_str, "hours": list(range(24)), "series": [], "error": str(e)})


# ---------------------------------------------------------------------------
# API — Weekly stats (Weekly tab chart)
# ---------------------------------------------------------------------------

@app.route("/api/stats/weekly")
def api_stats_weekly():
    """
    Return daily detection counts for the week containing the given date, grouped by species.
    Query param: date (YYYY-MM-DD, defaults to today UTC).
    Response: { week_start, week_end, days: [date_strings], series: [ {species, common_name, data: [counts]} ] }
    """
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Compute Monday–Sunday of the target week
    monday = target - timedelta(days=target.weekday())
    days = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week_start = days[0]
    week_end = days[6]

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get all detections in this week's range
        cursor.execute(
            """SELECT species, timestamp_utc
               FROM detections
               WHERE timestamp_utc >= ? AND timestamp_utc < ?
               ORDER BY timestamp_utc""",
            (f"{week_start}T00:00:00", f"{week_end}T23:59:59.999999")
        )
        rows = cursor.fetchall()
        conn.close()

        # Group by species and day
        species_days = {}  # { species_raw: { date_str: count } }
        for r in rows:
            sp_raw = r["species"]
            ts = r["timestamp_utc"]
            try:
                day_str = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            if sp_raw not in species_days:
                species_days[sp_raw] = {}
            species_days[sp_raw][day_str] = species_days[sp_raw].get(day_str, 0) + 1

        series = []
        for sp_raw, day_counts in species_days.items():
            sp = parse_species(sp_raw)
            series.append({
                "species": sp_raw,
                "common_name": sp["common_name"],
                "scientific_name": sp["scientific_name"],
                "data": [day_counts.get(d, 0) for d in days],
            })

        series.sort(key=lambda s: sum(s["data"]), reverse=True)

        return jsonify({
            "week_start": week_start,
            "week_end": week_end,
            "days": days,
            "series": series,
        })

    except sqlite3.OperationalError as e:
        logger.warning(f"Database read error: {e}")
        return jsonify({
            "week_start": week_start,
            "week_end": week_end,
            "days": days,
            "series": [],
            "error": str(e),
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("DASHBOARD_PORT", 7865))
    logger.info(f"Starting BirdListener Dashboard on port {port}")
    logger.info(f"Reading database from: {DB_PATH}")
    app.run(host="0.0.0.0", port=port, debug=False)
