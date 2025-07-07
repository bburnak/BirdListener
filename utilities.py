import logging
from pathlib import Path


def configure_logging(output_dir: str = None):
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    log_dir = Path(output_dir) if output_dir else Path.cwd()
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file_path = log_dir / "BirdListener.log"

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(console_handler)

    # Suppress absl logging messages to reduce verbosity from TensorFlow/BirdNET
    try:
        import absl.logging
        absl.logging.set_verbosity(absl.logging.ERROR)
        logging.getLogger('tensorflow').setLevel(logging.ERROR)
        logging.getLogger('h5py').setLevel(logging.ERROR)
    except ImportError:
        pass

    logger.info(f"Logging configured. Logs will be written to: {log_file_path}")