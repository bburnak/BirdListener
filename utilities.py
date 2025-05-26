import logging
import os


def configure_logging(output_dir: str = None):
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # If output_dir is provided, use it. Otherwise default to current dir.
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, 'BirdListener.log')
    else:
        log_path = 'BirdListener.log'

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear any existing handlers (to prevent duplication)
    logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

    # Console handler (same format as file)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(console_handler)
