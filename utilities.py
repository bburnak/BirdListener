import logging


def configure_logging():
    logging.basicConfig(
        filename='BirdListener.log',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
