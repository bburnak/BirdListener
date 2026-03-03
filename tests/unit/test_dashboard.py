"""
Unit tests for the BirdListener Dashboard Flask API.

Tests each API endpoint with a real in-memory SQLite database populated
with sample detection data. Follows the existing project test patterns.
"""

import json
import os
import sqlite3
import tempfile
import pytest

# Set the DB path env var before importing the app
_test_db_fd = None
_test_db_path = None


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Create a temporary SQLite database with sample data for each test."""
    db_path = str(tmp_path / "test_bird_detections.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            chunk_start_sec REAL NOT NULL,
            chunk_end_sec REAL NOT NULL,
            species TEXT NOT NULL,
            confidence REAL NOT NULL
        )
    """)

    # Insert sample detections spanning two days and multiple species
    sample_data = [
        # Day 1 — 2025-08-04, morning
        ("2025-08-04T06:00:00+00:00", 0.0,  3.0,  "Turdus merula_Eurasian Blackbird", 0.92),
        ("2025-08-04T06:00:00+00:00", 3.0,  6.0,  "Erithacus rubecula_European Robin", 0.85),
        ("2025-08-04T06:00:00+00:00", 6.0,  9.0,  "Turdus merula_Eurasian Blackbird", 0.78),
        # Day 1 — 2025-08-04, afternoon
        ("2025-08-04T14:00:00+00:00", 0.0,  3.0,  "Passer domesticus_House Sparrow", 0.71),
        ("2025-08-04T14:00:00+00:00", 3.0,  6.0,  "Turdus merula_Eurasian Blackbird", 0.88),
        # Day 2 — 2025-08-05, morning (also the "latest" detections)
        ("2025-08-05T07:00:00+00:00", 0.0,  3.0,  "Cyanistes caeruleus_Eurasian Blue Tit", 0.94),
        ("2025-08-05T07:00:00+00:00", 3.0,  6.0,  "Erithacus rubecula_European Robin", 0.81),
        ("2025-08-05T07:00:00+00:00", 6.0,  9.0,  "Cyanistes caeruleus_Eurasian Blue Tit", 0.76),
    ]

    cursor.executemany(
        "INSERT INTO detections (timestamp_utc, chunk_start_sec, chunk_end_sec, species, confidence) VALUES (?, ?, ?, ?, ?)",
        sample_data,
    )
    conn.commit()
    conn.close()

    # Patch the DB_PATH in the app module
    import dashboard.app as app_module
    original_path = app_module.DB_PATH
    app_module.DB_PATH = db_path
    yield db_path
    app_module.DB_PATH = original_path


@pytest.fixture
def client(setup_test_db):
    """Create a Flask test client."""
    from dashboard.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# parse_species tests
# ---------------------------------------------------------------------------

class TestParseSpecies:
    def test_standard_birdnet_format(self):
        from dashboard.app import parse_species
        result = parse_species("Turdus merula_Eurasian Blackbird")
        assert result["scientific_name"] == "Turdus merula"
        assert result["common_name"] == "Eurasian Blackbird"

    def test_no_underscore_fallback(self):
        from dashboard.app import parse_species
        result = parse_species("Sparrow")
        assert result["scientific_name"] == "Sparrow"
        assert result["common_name"] == "Sparrow"

    def test_multiple_underscores(self):
        """Only splits on the first underscore."""
        from dashboard.app import parse_species
        result = parse_species("Genus species_Common Name_Extra")
        assert result["scientific_name"] == "Genus species"
        assert result["common_name"] == "Common Name_Extra"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestIndexRoute:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"BirdListener" in resp.data


class TestConfigEndpoint:
    def test_returns_chunk_seconds_from_config(self, client, tmp_path):
        """When a valid config file exists, chunk_seconds comes from it."""
        config_path = str(tmp_path / "config.json")
        with open(config_path, "w") as f:
            json.dump({"chunk_seconds": 120, "sample_rate": 44100}, f)

        import dashboard.app as app_module
        original = app_module.CONFIG_PATH
        app_module.CONFIG_PATH = config_path
        try:
            resp = client.get("/api/config")
            data = json.loads(resp.data)
            assert data["chunk_seconds"] == 120
        finally:
            app_module.CONFIG_PATH = original

    def test_returns_default_when_config_missing(self, client):
        """When config file doesn't exist, returns the default chunk_seconds."""
        import dashboard.app as app_module
        original = app_module.CONFIG_PATH
        app_module.CONFIG_PATH = "/nonexistent/path/config.json"
        try:
            resp = client.get("/api/config")
            data = json.loads(resp.data)
            assert data["chunk_seconds"] == 300  # default
        finally:
            app_module.CONFIG_PATH = original

    def test_returns_default_when_config_invalid_json(self, client, tmp_path):
        """When config file contains invalid JSON, returns defaults."""
        bad_config = str(tmp_path / "bad.json")
        with open(bad_config, "w") as f:
            f.write("not valid json {{{")

        import dashboard.app as app_module
        original = app_module.CONFIG_PATH
        app_module.CONFIG_PATH = bad_config
        try:
            resp = client.get("/api/config")
            data = json.loads(resp.data)
            assert data["chunk_seconds"] == 300
        finally:
            app_module.CONFIG_PATH = original


class TestLatestDetections:
    def test_returns_latest_chunk(self, client):
        resp = client.get("/api/detections/latest")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "detections" in data
        assert "chunk_timestamp" in data
        # Latest timestamp should be from 2025-08-05
        assert "2025-08-05" in data["chunk_timestamp"]
        # All detections should be from the latest chunk
        for d in data["detections"]:
            assert "2025-08-05" in d["timestamp_utc"]

    def test_species_names_are_split(self, client):
        resp = client.get("/api/detections/latest")
        data = json.loads(resp.data)
        for d in data["detections"]:
            assert "common_name" in d
            assert "scientific_name" in d
            assert "_" not in d["common_name"] or " " in d["common_name"]

    def test_detections_sorted_by_confidence_desc(self, client):
        resp = client.get("/api/detections/latest")
        data = json.loads(resp.data)
        confs = [d["confidence"] for d in data["detections"]]
        assert confs == sorted(confs, reverse=True)


class TestDetectionsByDate:
    def test_filter_by_date(self, client):
        resp = client.get("/api/detections?date=2025-08-04")
        data = json.loads(resp.data)
        assert data["count"] > 0
        for d in data["detections"]:
            assert "2025-08-04" in d["timestamp_utc"]

    def test_filter_by_species(self, client):
        resp = client.get("/api/detections?species=Blackbird")
        data = json.loads(resp.data)
        assert data["count"] > 0
        for d in data["detections"]:
            assert "Blackbird" in d["common_name"]

    def test_limit_parameter(self, client):
        resp = client.get("/api/detections?limit=2")
        data = json.loads(resp.data)
        assert data["count"] <= 2

    def test_no_results_for_future_date(self, client):
        resp = client.get("/api/detections?date=2099-01-01")
        data = json.loads(resp.data)
        assert data["count"] == 0


class TestSpeciesList:
    def test_returns_all_species(self, client):
        resp = client.get("/api/species")
        data = json.loads(resp.data)
        assert data["count"] == 4  # Blackbird, Robin, Sparrow, Blue Tit
        assert len(data["species"]) == 4

    def test_species_have_required_fields(self, client):
        resp = client.get("/api/species")
        data = json.loads(resp.data)
        for sp in data["species"]:
            assert "common_name" in sp
            assert "scientific_name" in sp
            assert "total_detections" in sp
            assert "last_seen" in sp
            assert "avg_confidence" in sp

    def test_sorted_by_total_detections_desc(self, client):
        resp = client.get("/api/species")
        data = json.loads(resp.data)
        totals = [sp["total_detections"] for sp in data["species"]]
        assert totals == sorted(totals, reverse=True)


class TestDailyStats:
    def test_daily_returns_24_hours(self, client):
        resp = client.get("/api/stats/daily?date=2025-08-04")
        data = json.loads(resp.data)
        assert len(data["hours"]) == 24
        assert data["hours"] == list(range(24))

    def test_daily_has_correct_species(self, client):
        resp = client.get("/api/stats/daily?date=2025-08-04")
        data = json.loads(resp.data)
        common_names = {s["common_name"] for s in data["series"]}
        assert "Eurasian Blackbird" in common_names
        assert "European Robin" in common_names
        assert "House Sparrow" in common_names

    def test_daily_hour_counts(self, client):
        resp = client.get("/api/stats/daily?date=2025-08-04")
        data = json.loads(resp.data)
        # Blackbird: 2 at hour 6, 1 at hour 14
        blackbird = next(s for s in data["series"] if s["common_name"] == "Eurasian Blackbird")
        assert blackbird["data"][6] == 2
        assert blackbird["data"][14] == 1

    def test_empty_date_returns_no_series(self, client):
        resp = client.get("/api/stats/daily?date=2099-01-01")
        data = json.loads(resp.data)
        assert data["series"] == []


class TestWeeklyStats:
    def test_weekly_returns_7_days(self, client):
        resp = client.get("/api/stats/weekly?date=2025-08-04")
        data = json.loads(resp.data)
        assert len(data["days"]) == 7

    def test_weekly_has_correct_range(self, client):
        # 2025-08-04 is a Monday
        resp = client.get("/api/stats/weekly?date=2025-08-04")
        data = json.loads(resp.data)
        assert data["week_start"] == "2025-08-04"
        assert data["week_end"] == "2025-08-10"

    def test_weekly_has_species_data(self, client):
        resp = client.get("/api/stats/weekly?date=2025-08-04")
        data = json.loads(resp.data)
        assert len(data["series"]) > 0

    def test_invalid_date_returns_error(self, client):
        resp = client.get("/api/stats/weekly?date=not-a-date")
        assert resp.status_code == 400


class TestEmptyDatabase:
    """Test behavior when the database has no detections."""

    @pytest.fixture(autouse=True)
    def empty_db(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                chunk_start_sec REAL NOT NULL,
                chunk_end_sec REAL NOT NULL,
                species TEXT NOT NULL,
                confidence REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        import dashboard.app as app_module
        original_path = app_module.DB_PATH
        app_module.DB_PATH = db_path
        yield
        app_module.DB_PATH = original_path

    def test_latest_empty(self, client):
        resp = client.get("/api/detections/latest")
        data = json.loads(resp.data)
        assert data["detections"] == []
        assert data["chunk_timestamp"] is None

    def test_species_empty(self, client):
        resp = client.get("/api/species")
        data = json.loads(resp.data)
        assert data["species"] == []
        assert data["count"] == 0

    def test_daily_empty(self, client):
        resp = client.get("/api/stats/daily?date=2025-08-04")
        data = json.loads(resp.data)
        assert data["series"] == []

    def test_weekly_empty(self, client):
        resp = client.get("/api/stats/weekly?date=2025-08-04")
        data = json.loads(resp.data)
        assert data["series"] == []
