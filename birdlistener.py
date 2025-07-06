import logging
import queue
import threading
import tempfile
import os
import sounddevice as sd
import numpy as np
import soundfile as sf
from pathlib import Path
from collections import deque
import absl.logging
absl.logging.set_verbosity(absl.logging.ERROR)
from birdnet import SpeciesPredictions, predict_species_within_audio_file
from datetime import datetime, timezone
from detection import BirdDetection

logger = logging.getLogger(__name__)


class BirdListener:
    def __init__(self):
        self.fs = 44100  # Sample rate
        self.channels = 1
        self.blocksize = 1024
        self.chunk_seconds = 15
        self.chunk_samples = self.chunk_seconds * self.fs
        self.detection_threshold = 0.7
        self.detections = []

        # Initialize an empty buffer
        self.audio_buffer = deque(maxlen=self.chunk_samples)


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
            logger.info(f"Stream status: {status}")

        # Flatten input to mono (indata is shape [frames, channels])
        self.audio_buffer.extend(indata[:, 0])  # Extract mono channel

        if len(self.audio_buffer) >= self.chunk_samples:
            # Extract chunk
            audio_chunk = [self.audio_buffer.popleft() for _ in range(self.chunk_samples)]
            audio_array = np.array(audio_chunk, dtype='float32').reshape(-1, 1)
            self._save_chunk_to_queue(audio_array)

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
        logger.info("Real-time analysis stopped.")

    def _append_detection(self,
                          chunk: tuple,
                          prediction: str,
                          confidence: float):
        logger.info("Saving detection.")
        self.detections.append(
            BirdDetection(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                chunk_interval_sec=chunk,
                species=prediction,
                confidence=confidence
            )
        )


    def analyze(self, audio_path: Path):
        logger.info("Identifying species...")
        prediction_chunks = SpeciesPredictions(predict_species_within_audio_file(audio_path))
        for chunk, predictions in prediction_chunks.items():
            if not predictions:
                logger.info(f"No prediction returned for the subchunk {chunk}")
            else:
                prediction, confidence = next(iter(predictions.items()))
                logger.info(f"Predicted '{prediction}' with confidence {confidence:.2f}")
                if confidence > self.detection_threshold:
                    logger.info("Confidence is greater than detection threshold!")
                    self._append_detection(
                        chunk,
                        prediction,
                        confidence
                    )

        os.remove(audio_path)  # Clean up here

    def run(self):
        logger.info("Starting BirdListener run loop...")
        self._running = True
        self._thread = threading.Thread(target=self._process_audio, daemon=True)
        self._thread.start()
        self.listen()
        logger.info("BirdListener run completed.")
