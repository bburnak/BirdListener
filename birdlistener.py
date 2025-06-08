import logging
import queue
import threading
import tempfile
import os
import sounddevice as sd
import numpy as np
import soundfile as sf
from pathlib import Path
import absl.logging
absl.logging.set_verbosity(absl.logging.ERROR)
from birdnet import SpeciesPredictions, predict_species_within_audio_file

logger = logging.getLogger(__name__)


class BirdListener:
    def __init__(self):
        self.fs = 44100  # Sample rate
        self.channels = 1
        self.blocksize = 1024
        self.chunk_seconds = 60
        self.chunk_samples = self.chunk_seconds * self.fs

        # Initialize an empty buffer
        self.audio_buffer = np.zeros((0, self.channels), dtype='float32')

        self._stream = None
        self._running = False
        self._queue = queue.Queue()

    def listen(self):
        self._stream = sd.InputStream(
            samplerate=self.fs,
            blocksize=self.blocksize,
            channels=self.channels,
            callback=self._callback
        )
        self._stream.start()
        logger.info("Real-time analysis started...")

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"Stream status: {status}")

        self.audio_buffer = np.vstack([self.audio_buffer, indata])

        if len(self.audio_buffer) >= self.chunk_samples:
            buffer_copy = self.audio_buffer[:self.chunk_samples].copy()
            self.audio_buffer = self.audio_buffer[int(0.5 * self.chunk_samples):]
            self._save_chunk_to_queue(buffer_copy)  # fast

    def _save_chunk_to_queue(self, audio_data):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            sf.write(tmpfile.name, audio_data, self.fs)
            self._queue.put(tmpfile.name)

    def _process_audio(self):
        while self._running:
            try:
                audio_path = self._queue.get(timeout=100)
                self.analyze(Path(audio_path))
            except queue.Empty:
                continue

    def stop(self):
        self._running = False
        self._stream.stop()
        self._stream.close()
        print("Real-time analysis stopped.")


    def analyze(self, audio_path: Path):
        logger.info("Identifying species...")
        predictions = SpeciesPredictions(predict_species_within_audio_file(audio_path))
        prediction, confidence = list(predictions[(0.0, 3.0)].items())[0]
        logger.info(f"Predicted '{prediction}' with confidence {confidence:.2f}")
        os.remove(audio_path)  # Clean up here

    def run(self):
        logger.info("Starting BirdListener run loop...")
        self._running = True
        self._thread = threading.Thread(target=self._process_audio, daemon=True)
        self._thread.start()
        self.listen()
        logger.info("BirdListener run completed.")
