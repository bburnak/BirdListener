import logging
import queue
import threading
import tempfile
import os
import sounddevice as sd
import numpy as np
import soundfile as sf
from pathlib import Path
import birdnet
from datetime import datetime, timezone
from birdcode.detection import BirdDetection
from birdcode.database import DatabaseWriter


logger = logging.getLogger(__name__)


class BirdListener:
    def __init__(self, db_file: str, config: dict, audio_input_device: int = None):
        """
        Initializes the BirdListener with audio and database configurations.

        Args:
            db_file (str): The path to the SQLite database file.
            config (dict): Configurations.
            audio_input_device (int, optional): The ID of the audio input device
                                                to use. If None, the default device is used.
        """
        self.fs = config.get("sample_rate", 44100)  # Sample rate
        self.channels = config.get("channels", 1)
        self.blocksize = config.get("blocksize", 1024)
        self.chunk_seconds = config.get("chunk_seconds", 180)
        self.chunk_samples = self.chunk_seconds * self.fs
        self.detection_threshold = config.get("detection_threshold", 0.7)
        self.audio_input_device = audio_input_device

        # Load BirdNET acoustic model ("tf" = TFLite for RPi/low-memory, "pb" = ProtoBuf for GPU)
        model_backend = config.get("model_backend", "tf")
        self._model = birdnet.load("acoustic", "2.4", model_backend)

        # Pre-allocated numpy buffer for accumulating audio data (memory-efficient)
        self.audio_buffer = np.zeros(self.chunk_samples, dtype='float32')
        self._buffer_pos = 0

        self._stream = None
        self._running = False

        # Queue for temporary audio chunk file paths to be analyzed by BirdNET
        self._audio_chunk_queue = queue.Queue()

        # Database integration components
        self._db_write_queue = queue.Queue()  # Queue for BirdDetection objects
        self._db_writer = DatabaseWriter(db_file, self._db_write_queue)

        # Thread for processing audio chunks and running BirdNET analysis
        self._audio_process_thread = None

    def listen(self):
        """
        Starts the real-time audio input stream.
        """
        try:
            self._stream = sd.InputStream(
                samplerate=self.fs,
                blocksize=self.blocksize,
                channels=self.channels,
                callback=self._callback,
                device=self.audio_input_device
            )
            self._stream.start()
            logger.info("Real-time audio analysis started...")
            if self.audio_input_device is not None:
                logger.info(f"Listening on audio device ID: {self.audio_input_device}")
            else:
                logger.info("Listening on default audio device.")
        except Exception as e:
            logger.critical(f"Failed to start audio stream: {e}", exc_info=True)
            self._running = False

    def _callback(self, indata, frames, time, status):
        """
        Callback function for the sounddevice input stream.
        Writes audio data into a pre-allocated numpy buffer and queues
        chunks for analysis when full.
        """
        if status:
            logger.info(f"Stream status: {status}")

        # Flatten input to mono
        samples = indata[:, 0]
        n = len(samples)
        end = self._buffer_pos + n

        if end < self.chunk_samples:
            # Common path: samples fit in the remaining buffer space
            self.audio_buffer[self._buffer_pos:end] = samples
            self._buffer_pos = end
        else:
            # Buffer is full — fill remaining space, queue the chunk, start fresh
            fit = self.chunk_samples - self._buffer_pos
            self.audio_buffer[self._buffer_pos:] = samples[:fit]

            audio_array = self.audio_buffer.copy().reshape(-1, 1)
            self._save_chunk_to_queue(audio_array)

            # Store any leftover samples from this callback into the reset buffer
            remainder = n - fit
            if remainder > 0:
                self.audio_buffer[:remainder] = samples[fit:]
            self._buffer_pos = remainder

    def _save_chunk_to_queue(self, audio_data: np.ndarray):
        """
        Saves an audio chunk to a temporary WAV file and adds its path to the audio chunk queue.
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
                sf.write(tmpfile.name, audio_data, self.fs)
                self._audio_chunk_queue.put(tmpfile.name)
        except Exception as e:
            logger.error(f"Error saving audio chunk to temporary file: {e}", exc_info=True)

    def _process_audio(self):
        """
        Worker thread function to retrieve audio chunk paths from the queue,
        run BirdNET analysis, and queue detections for database writing.
        """
        while self._running:
            try:
                audio_path = self._audio_chunk_queue.get(timeout=5)  # Wait for a chunk with a timeout
                self.analyze(Path(audio_path))  # Perform BirdNET analysis
                self._audio_chunk_queue.task_done()  # Mark task as complete for queue.join()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio processing thread while analyzing {audio_path}: {e}", exc_info=True)
                # Ensure the temporary file is removed even on error if possible
                if 'audio_path' in locals() and os.path.exists(audio_path):
                    os.remove(audio_path)

    def stop(self):
        """
        Gracefully stops all running threads and releases resources.
        """
        self._running = False
        logger.info("Signaling BirdListener threads to stop...")

        # 1. Stop audio input stream
        if self._stream and self._stream.active:
            self._stream.stop()
            self._stream.close()
            logger.info("Audio stream stopped and closed.")

        # 2. Give the audio processing thread a chance to finish current tasks
        deadline = 10  # seconds to wait for queue to drain
        import time as _time
        waited = 0
        while not self._audio_chunk_queue.empty() and waited < deadline:
            _time.sleep(0.5)
            waited += 0.5
        if self._audio_chunk_queue.empty():
            logger.info("Audio chunk queue processed pending tasks.")
        else:
            logger.warning(
                "Audio processing queue not empty on shutdown, some tasks might be unfinished.")

        # 3. Stop the database writer gracefully
        # This will also ensure any buffered detections are flushed to disk.
        self._db_writer.stop()
        logger.info("Database writer stopped.")

        # 4. Join the audio processing thread (wait for it to fully exit)
        if self._audio_process_thread and self._audio_process_thread.is_alive():
            self._audio_process_thread.join(timeout=5)  # Give it a little time to finish its loop
            if self._audio_process_thread.is_alive():
                logger.warning("Audio processing thread did not terminate within timeout.")
            else:
                logger.info("Audio processing thread terminated.")

        logger.info("BirdListener resources released.")

    @staticmethod
    def _parse_time_to_seconds(time_value):
        """Parse a time value to float seconds. Handles 'HH:MM:SS.ss' strings and numeric types."""
        if isinstance(time_value, (int, float, np.floating, np.integer)):
            return float(time_value)
        parts = str(time_value).split(':')
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

    def analyze(self, audio_path: Path):
        """
        Performs BirdNET analysis on a given audio file and queues detected birds
        for database writing.
        """
        logger.info(f"Identifying species in {audio_path.name}...")
        try:
            # Call BirdNET model to get predictions
            predictions = self._model.predict(
                audio_path,
                default_confidence_threshold=0.01,  # Low threshold — we filter ourselves
            )
            result_array = predictions.to_structured_array()
        except Exception as e:
            logger.error(f"Error during BirdNET analysis of {audio_path}: {e}", exc_info=True)
            os.remove(audio_path)  # Clean up temp file even on analysis error
            return

        detected_in_chunk = False
        for row in result_array:
            species = str(row['species_name'])
            confidence = float(row['confidence'])
            start_sec = self._parse_time_to_seconds(row['start_time'])
            end_sec = self._parse_time_to_seconds(row['end_time'])

            logger.info(f"Predicted '{species}' with confidence {confidence:.2f}")
            if confidence > self.detection_threshold:
                logger.info("Confidence is greater than detection threshold!")

                # Create a BirdDetection object
                detection_obj = BirdDetection(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),  # Current UTC time
                    chunk_interval_sec=(start_sec, end_sec),  # Tuple (start_sec, end_sec)
                    species=species,
                    confidence=confidence
                )

                # Put the BirdDetection object into the database write queue
                # This is a non-blocking operation.
                self._db_write_queue.put(detection_obj)
                detected_in_chunk = True

        if not detected_in_chunk:
            logger.info(f"No strong predictions found for audio chunk {audio_path.name}.")

        os.remove(audio_path)  # Clean up the temporary audio file after analysis


    def run(self):
        """
        Starts the BirdListener application by launching necessary threads
        and the audio input stream.
        """
        logger.info("Starting BirdListener application components...")
        self._running = True

        # 1. Start the DatabaseWriter thread FIRST.
        self._db_writer.start()
        logger.info("DatabaseWriter thread started.")

        # 2. Start the audio processing thread.
        self._audio_process_thread = threading.Thread(target=self._process_audio, daemon=True)
        self._audio_process_thread.start()
        logger.info("Audio processing thread started.")

        # 3. Start the audio input stream.
        self.listen()
        logger.info("BirdListener's main 'run' method completed its setup phase (audio stream is active).")
