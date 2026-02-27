import unittest
from unittest.mock import patch, MagicMock, call
import numpy as np
import queue
from pathlib import Path
from birdcode.birdlistener import BirdListener

class TestBirdListener(unittest.TestCase):
    def setUp(self):
        self.config = {
            "sample_rate": 8000,
            "channels": 1,
            "blocksize": 256,
            "chunk_seconds": 1,
            "detection_threshold": 0.5
        }
        self.db_file = ":memory:"

    @patch("birdcode.birdlistener.birdnet")
    @patch("birdcode.birdlistener.DatabaseWriter")
    def test_init_sets_attributes(self, mock_db_writer, mock_birdnet):
        bl = BirdListener(self.db_file, self.config, audio_input_device=2)
        self.assertEqual(bl.fs, 8000)
        self.assertEqual(bl.channels, 1)
        self.assertEqual(bl.blocksize, 256)
        self.assertEqual(bl.chunk_seconds, 1)
        self.assertEqual(bl.chunk_samples, 8000)
        self.assertEqual(bl.detection_threshold, 0.5)
        self.assertEqual(bl.audio_input_device, 2)
        self.assertIsInstance(bl.audio_buffer, np.ndarray)
        self.assertEqual(bl.audio_buffer.shape, (8000,))
        self.assertEqual(bl.audio_buffer.dtype, np.float32)
        self.assertEqual(bl._buffer_pos, 0)
        self.assertIsInstance(bl._audio_chunk_queue, queue.Queue)
        self.assertIsInstance(bl._db_write_queue, queue.Queue)
        mock_db_writer.assert_called_once_with(self.db_file, bl._db_write_queue)

    @patch("birdcode.birdlistener.birdnet")
    @patch("birdcode.birdlistener.sd.InputStream")
    @patch("birdcode.birdlistener.DatabaseWriter")
    def test_listen_starts_stream(self, mock_db_writer, mock_input_stream, mock_birdnet):
        bl = BirdListener(self.db_file, self.config)
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream
        bl.listen()
        mock_input_stream.assert_called_once()
        mock_stream.start.assert_called_once()

    @patch("birdcode.birdlistener.birdnet")
    @patch("birdcode.birdlistener.sf.write")
    @patch("birdcode.birdlistener.tempfile.NamedTemporaryFile")
    @patch("birdcode.birdlistener.DatabaseWriter")
    def test_save_chunk_to_queue(self, mock_db_writer, mock_tempfile, mock_sf_write, mock_birdnet):
        bl = BirdListener(self.db_file, self.config)
        mock_file = MagicMock()
        mock_file.name = "temp.wav"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        arr = np.zeros((bl.chunk_samples, 1), dtype='float32')
        bl._save_chunk_to_queue(arr)
        mock_sf_write.assert_called_once_with("temp.wav", arr, bl.fs)
        self.assertFalse(bl._audio_chunk_queue.empty())
        self.assertEqual(bl._audio_chunk_queue.get(), "temp.wav")

    @patch("birdcode.birdlistener.birdnet")
    @patch("birdcode.birdlistener.BirdDetection")
    @patch("birdcode.birdlistener.DatabaseWriter")
    def test_analyze_detects_and_queues(self, mock_db_writer, mock_bird_detection, mock_birdnet):
        bl = BirdListener(self.db_file, self.config)
        bl.detection_threshold = 0.1  # Lower for test
        audio_path = Path("fake.wav")

        # Build a mock structured array matching birdnet 0.2.x output
        mock_result_array = np.array(
            [("fake.wav", "00:00:00.00", "00:00:03.00", "Sparrow", 0.9)],
            dtype=[
                ("file_path", "U256"), ("start_time", "U16"),
                ("end_time", "U16"), ("species_name", "U256"),
                ("confidence", "f4"),
            ],
        )
        mock_predictions = MagicMock()
        mock_predictions.to_structured_array.return_value = mock_result_array
        bl._model = MagicMock()
        bl._model.predict.return_value = mock_predictions

        mock_detection_obj = MagicMock()
        mock_bird_detection.return_value = mock_detection_obj
        with patch("os.remove") as mock_remove:
            bl.analyze(audio_path)
            self.assertFalse(bl._db_write_queue.empty())
            self.assertIs(bl._db_write_queue.get(), mock_detection_obj)
            mock_remove.assert_called_once_with(audio_path)

    @patch("birdcode.birdlistener.birdnet")
    @patch("birdcode.birdlistener.DatabaseWriter")
    def test_stop_stops_threads_and_stream(self, mock_db_writer, mock_birdnet):
        bl = BirdListener(self.db_file, self.config)
        bl._stream = MagicMock()
        bl._stream.active = True
        bl._audio_process_thread = MagicMock()
        bl._audio_process_thread.is_alive.return_value = False
        bl._db_writer = MagicMock()
        bl.stop()
        bl._stream.stop.assert_called_once()
        bl._stream.close.assert_called_once()
        bl._db_writer.stop.assert_called_once()

if __name__ == "__main__":
    unittest.main()
