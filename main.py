import argparse
import logging
from birdlistener import BirdListener


logger = logging.getLogger(__name__)


def run():
    parser = argparse.ArgumentParser(
        prog='BirdListener',
        description='Listens to the birds, let\'s you know where they are. Like NSA of birds.',
        epilog='Not sure what this text does.')
    parser.add_argument('-i', '--input')
    parser.add_argument('-o', '--output')
    parser.add_argument('-a', '--audio')
    args = parser.parse_args()
    logger.info(f"Parsed arguments: input={args.input}, output={args.output}, audio={args.audio}")

    BirdListener().run()


if __name__ == '__main__':
    logging.basicConfig(
        filename='BirdListener.log',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    run()
