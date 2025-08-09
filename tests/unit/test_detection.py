import unittest
from birdcode.detection import BirdDetection

class TestBirdDetection(unittest.TestCase):
    def setUp(self):
        self.timestamp = "2025-08-09T12:00:00Z"
        self.chunk_interval = (0, 10)
        self.species = "Sparrow"
        self.confidence = 0.85

    def test_initialization_and_attributes(self):
        bd = BirdDetection(self.timestamp, self.chunk_interval, self.species, self.confidence)
        self.assertEqual(bd.timestamp_utc, self.timestamp)
        self.assertEqual(bd.chunk_interval_sec, self.chunk_interval)
        self.assertEqual(bd.species, self.species)
        self.assertEqual(bd.confidence, self.confidence)

    def test_repr(self):
        bd = BirdDetection(self.timestamp, self.chunk_interval, self.species, self.confidence)
        rep = repr(bd)
        self.assertIn("BirdDetection", rep)
        self.assertIn(self.species, rep)
        self.assertIn(str(self.confidence), rep)
        self.assertIn(str(self.chunk_interval), rep)
        self.assertIn(self.timestamp, rep)

    def test_slots(self):
        bd = BirdDetection(self.timestamp, self.chunk_interval, self.species, self.confidence)
        # __slots__ prevents adding new attributes
        with self.assertRaises(AttributeError):
            bd.new_attr = 123

if __name__ == "__main__":
    unittest.main()
