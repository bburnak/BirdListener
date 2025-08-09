import pytest
import queue
import sqlite3
from birdcode.database import DatabaseWriter

class DummyDetection:
    def __init__(self, timestamp_utc, chunk_interval_sec, species, confidence):
        self.timestamp_utc = timestamp_utc
        self.chunk_interval_sec = chunk_interval_sec
        self.species = species
        self.confidence = confidence

@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_detections.db")

@pytest.fixture
def write_queue():
    return queue.Queue()

@pytest.fixture
def db_writer(test_db_path, write_queue):
    writer = DatabaseWriter(test_db_path, write_queue, batch_size=2, flush_interval=2)
    return writer

def test_initialize_db_creates_table(db_writer, test_db_path):
    db_writer._initialize_db()
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detections'")
    assert cursor.fetchone() is not None
    conn.close()

def test_write_batch_inserts_data(db_writer, test_db_path):
    db_writer._initialize_db()
    d1 = DummyDetection('2025-08-04T12:00:00Z', (0, 10), 'sparrow', 0.95)
    d2 = DummyDetection('2025-08-04T12:01:00Z', (10, 20), 'robin', 0.90)
    db_writer._buffer = [d1, d2]
    db_writer._write_batch()
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM detections")
    count = cursor.fetchone()[0]
    assert count == 2
    conn.close()

def test_writer_loop_writes_from_queue(db_writer, write_queue, test_db_path):
    d1 = DummyDetection('2025-08-04T12:00:00Z', (0, 10), 'sparrow', 0.95)
    d2 = DummyDetection('2025-08-04T12:01:00Z', (10, 20), 'robin', 0.90)
    write_queue.put(d1)
    write_queue.put(d2)
    db_writer.start()
    write_queue.join() # Wait for queue to be processed
    db_writer.stop()
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM detections")
    count = cursor.fetchone()[0]
    assert count == 2
    conn.close()
