import logging
from pathlib import Path
from birdnet import SpeciesPredictions, predict_species_within_audio_file

logger = logging.getLogger(__name__)


class BirdListener:
    def __init__(self):
        self.something = 0
        logger.info("BirdListener initialized.")

    def listen(self):
        logger.info("Listening... (placeholder)")
        # implement microphone/audio handling here

    def identify(self):
        logger.info("Identifying species...")
        audio_path = Path("C:\\Users\\baris\\Downloads\\soundscape.wav")
        predictions = SpeciesPredictions(predict_species_within_audio_file(audio_path))
        prediction, confidence = list(predictions[(0.0, 3.0)].items())[0]
        logger.info(f"Predicted '{prediction}' with confidence {confidence:.2f}")

    def notify(self):
        logger.info("Notifying user... (placeholder)")

    def run(self):
        logger.info("Starting BirdListener run loop...")
        self.listen()
        self.identify()
        self.notify()
        logger.info("BirdListener run completed.")
