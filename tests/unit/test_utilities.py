import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import logging
import json
from pathlib import Path
import sys

import birdcode.utilities as utils

class TestUtilities(unittest.TestCase):
    def setUp(self):
        # Remove all handlers before each test
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    def test_configure_logging_creates_handlers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            utils.configure_logging(tmpdir)
            logger = logging.getLogger()
            handler_types = {type(h) for h in logger.handlers}
            self.assertIn(logging.FileHandler, handler_types)
            self.assertIn(logging.StreamHandler, handler_types)
            # Close all handlers to release file lock before checking file existence
            for handler in logger.handlers:
                handler.flush()
                handler.close()
            log_path = Path(tmpdir) / "BirdListener.log"
            self.assertTrue(log_path.exists())
            # Remove handlers after test to avoid side effects
            logger.handlers.clear()

    def test_configure_logging_default_dir(self):
        utils.configure_logging()
        logger = logging.getLogger()
        handler_types = {type(h) for h in logger.handlers}
        self.assertIn(logging.FileHandler, handler_types)
        self.assertIn(logging.StreamHandler, handler_types)

    def test_get_config_reads_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"
            data = {"foo": "bar", "num": 42}
            with open(config_path, "w") as f:
                json.dump(data, f)
            result = utils.get_config(config_path)
            self.assertEqual(result, data)

    @patch("birdcode.utilities.logging.warning")
    def test_get_config_fallback_to_default(self, mock_warning):
        # Simulate missing file, should fallback to cwd/config/config.json
        with patch("builtins.open", mock_open(read_data='{"a":1}')) as m:
            fake_path = Path("not_exist.json")
            with patch.object(Path, "exists", return_value=False):
                with patch("pathlib.Path.cwd", return_value=Path("/tmp")):
                    result = utils.get_config(fake_path)
                    self.assertEqual(result, {"a": 1})
                    mock_warning.assert_called()

if __name__ == "__main__":
    unittest.main()
