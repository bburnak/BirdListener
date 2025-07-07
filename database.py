import logging
import queue
import threading
import absl.logging
absl.logging.set_verbosity(absl.logging.ERROR)
import sqlite3
from datetime import datetime


logger = logging.getLogger(__name__)


class DatabaseWriter:
    def __init__(self,
                 db_file: str,
                 write_queue: queue.Queue,
                 batch_size: int = 100,
                 flush_interval: int = 30
                 ):
        self.db_file = db_file
        self.write_queue = write_queue # The queue to read from
        self.batch_size = batch_size   # How many detections to accumulate before writing
        self.flush_interval = flush_interval # How often to force a write even if batch_size not met
        self._running = False
        self._conn = None
        self._cursor = None
        self._buffer = [] # Temporary buffer for accumulating detections

    def _initialize_db(self):
        """Initializes the SQLite database connection and creates the table."""
        try:
            self._conn = sqlite3.connect(self.db_file, timeout=10) # Add a timeout for connection
            self._cursor = self._conn.cursor()
            self._cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT NOT NULL,
                    chunk_start_sec REAL NOT NULL,
                    chunk_end_sec REAL NOT NULL,
                    species TEXT NOT NULL,
                    confidence REAL NOT NULL
                )
            """)
            self._conn.commit()
            logger.info(f"Database '{self.db_file}' initialized successfully.")
        except sqlite3.Error as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise # Re-raise to stop the application if DB init fails

    def _write_batch(self):
        """Writes the accumulated detections from the buffer to the database."""
        if not self._buffer:
            return

        try:
            self._cursor.executemany(
                "INSERT INTO detections (timestamp_utc, chunk_start_sec, chunk_end_sec, species, confidence) VALUES (?, ?, ?, ?, ?)",
                [(d.timestamp_utc, d.chunk_interval_sec[0], d.chunk_interval_sec[1], d.species, d.confidence)
                 for d in self._buffer]
            )
            self._conn.commit()
            logger.info(f"Successfully wrote {len(self._buffer)} detections to database.")
            self._buffer.clear() # Clear buffer after successful write
        except sqlite3.Error as e:
            logger.error(f"Failed to write batch to database: {e}")
            # Depending on criticality, you might want to re-add items to queue or log them for later recovery

    def _run_writer_loop(self):
        """The main loop for the database writing thread."""
        self._initialize_db()
        last_flush_time = datetime.now()

        while self._running:
            try:
                # Try to get items from the queue with a timeout
                detection = self.write_queue.get(timeout=1) # Wait for 1 second
                self._buffer.append(detection)
                self.write_queue.task_done() # Mark task as done for join() later

                # Check if batch size is met
                if len(self._buffer) >= self.batch_size:
                    self._write_batch()
                    last_flush_time = datetime.now() # Reset timer after batch write

            except queue.Empty:
                # If no items in queue for a while, check flush interval
                if (datetime.now() - last_flush_time).total_seconds() >= self.flush_interval:
                    self._write_batch()
                    last_flush_time = datetime.now()
            except Exception as e:
                logger.error(f"Error in DatabaseWriter loop: {e}")
                # Consider specific error handling, e.g., if DB connection breaks

        # After the loop, write any remaining items in the buffer
        self._write_batch()
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed.")

    def start(self):
        """Starts the database writing thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_writer_loop, daemon=True)
        self._thread.start()
        logger.info("DatabaseWriter thread started.")

    def stop(self):
        """Stops the database writing thread and flushes remaining data."""
        self._running = False
        # Give the thread a chance to process remaining queue items and buffer
        self._thread.join(timeout=self.flush_interval + 5) # Wait a bit longer than flush interval
        logger.info("DatabaseWriter thread stopped.")