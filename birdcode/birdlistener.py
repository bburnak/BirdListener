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
from birdnet import SpeciesPredictions, predict_species_within_audio_file
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

        # Buffer for accumulating audio data before processing
        self.audio_buffer = deque(maxlen=self.chunk_samples)

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
        Appends audio data to a buffer and queues chunks for analysis.
        """
        if status:
            logger.info(f"Stream status: {status}")

        # Flatten input to mono
        self.audio_buffer.extend(indata[:, 0])

        # When enough audio data is accumulated, save it to a temp file and queue for analysis
        if len(self.audio_buffer) >= self.chunk_samples:
            audio_chunk = [self.audio_buffer.popleft() for _ in range(self.chunk_samples)]
            audio_array = np.array(audio_chunk, dtype='float32').reshape(-1, 1)
            self._save_chunk_to_queue(audio_array)

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
                audio_path = self._audio_chunk_queue.get(timeout=100)  # Wait for a chunk with a timeout
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
        try:
            # This join ensures any items already put on the queue are processed
            self._audio_chunk_queue.join(timeout=10)
            logger.info("Audio chunk queue processed pending tasks.")
        except RuntimeError:
            logger.warning(
                "Audio processing queue not empty or already joined on shutdown, some tasks might be unfinished.")

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

    def analyze(self, audio_path: Path):
        """
        Performs BirdNET analysis on a given audio file and queues detected birds
        for database writing.
        """
        logger.info(f"Identifying species in {audio_path.name}...")
        try:
            # Call BirdNET to get raw predictions
            predictions_raw = predict_species_within_audio_file(audio_path)
            # Process raw predictions into SpeciesPredictions object
            prediction_chunks = SpeciesPredictions(predictions_raw)
        except Exception as e:
            logger.error(f"Error during BirdNET analysis of {audio_path}: {e}", exc_info=True)
            os.remove(audio_path)  # Clean up temp file even on analysis error
            return

        detected_in_chunk = False
        for chunk_interval, chunk_predictions in prediction_chunks.items():
            if not chunk_predictions:
                logger.info(f"No prediction returned for chunk interval {chunk_interval}")
            else:
                prediction_species, prediction_confidence = next(iter(chunk_predictions.items()))
                logger.info(f"Predicted '{prediction_species}' with confidence {prediction_confidence:.2f}")
                if prediction_confidence > self.detection_threshold:
                    logger.info("Confidence is greater than detection threshold!")

                    # Create a BirdDetection object
                    detection_obj = BirdDetection(
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),  # Current UTC time
                        chunk_interval_sec=chunk_interval,  # Tuple (start_sec, end_sec)
                        species=prediction_species,
                        confidence=prediction_confidence
                    )

                    # Put the BirdDetection object into the database write queue
                    # This is a non-blocking operation.
                    self._db_write_queue.put(detection_obj)
                    detected_in_chunk = True

        if not detected_in_chunk:
            logger.info(f"No strong predictions found for audio chunk {audio_path.name}.")

        os.remove(audio_path)  # Clean up the temporary audio file after analysis

    # def analyze(self, audio_path: Path):
    #     logger.info("Identifying species...")
    #     prediction_chunks = SpeciesPredictions(predict_species_within_audio_file(audio_path))
    #     for chunk, predictions in prediction_chunks.items():
    #         if not predictions:
    #             logger.info(f"No prediction returned for the subchunk {chunk}")
    #         else:
    #             prediction, confidence = next(iter(predictions.items()))
    #             logger.info(f"Predicted '{prediction}' with confidence {confidence:.2f}")
    #             if confidence > self.detection_threshold:
    #                 logger.info("Confidence is greater than detection threshold!")
    #                 # self._append_detection(
    #                 #     chunk,
    #                 #     prediction,
    #                 #     confidence
    #                 # )
    #
    #     os.remove(audio_path)  # Clean up here


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
