import logging
import queue
import threading
import sounddevice as sd
import numpy as np
from pathlib import Path
from birdnet import SpeciesPredictions, predict_species_within_audio_file


logger = logging.getLogger(__name__)


class BirdListener:
    def __init__(self, samplerate=44100, blocksize=1024, channels=1):
        self.fs = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.q = queue.Queue()
        self._running = False
        self._stream = None

    def start(self):
        self._running = True
        threading.Thread(target=self._process_audio, daemon=True).start()
        self._stream = sd.InputStream(
            samplerate=self.fs,
            blocksize=self.blocksize,
            channels=self.channels,
            callback=self._callback
        )
        self._stream.start()
        logger.info("Real-time analysis started...")

    def _process_audio(self):
        while self._running:
            try:
                block = self.q.get(timeout=0.5)
                self.analyze(block)
            except queue.Empty:
                continue

    def _callback(self, indata, frames, time, status):
        if status:
            logger.info(f"Status: {status}")
        self.q.put(indata.copy())


    def analyze(self, audio_block):
        """Override this for real-time audio analysis."""
        # Example: RMS energy
        rms = np.sqrt(np.mean(audio_block**2))
        logger.info(f"RMS energy: {rms:.5f}")

        # 🔁 Replace this with model inference, etc.


    def stop(self):
        self._running = False
        self._stream.stop()
        self._stream.close()
        print("Real-time analysis stopped.")


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
        # self.start()
        # self.identify()
        # self.notify()
        logger.info("BirdListener run completed.")
