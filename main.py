import argparse
import logging
import sys
import time
from pathlib import Path
from birdcode import utilities
from birdcode.birdlistener import BirdListener

logger = logging.getLogger(__name__)


def main():
    """
    Main function to parse arguments, initialize logging,
    create and run the BirdListener application, and manage its shutdown.
    """
    parser = argparse.ArgumentParser(
        prog='BirdListener',
        description='Listens to the birds and identifies species in real-time.',
        epilog='Use Ctrl+C to gracefully stop the application. Find available audio devices with `python -m '
               'sounddevice`.'
    )

    # Placeholder for an input source #TODO: config file will be read from here.
    parser.add_argument(
        '-i', '--input',
        type=str,
        help='Placeholder for an input source (currently unused by BirdListener core logic).'
    )

    # Base directory for logs and the database file
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='.',  # Default to current directory
        help='Base directory to store logs and results (e.g., database file, defaults to current directory).'
    )

    # Audio input device ID
    parser.add_argument(
        '-a', '--audio',
        type=int,
        default=None,
        help='Specify the input audio device ID. Use `python -m sounddevice` to list devices.'
    )

    # Database name
    parser.add_argument(
        '-d', '--database',
        type=str,
        default="bird_detections",
        help="Specify database to record statistically significant bird detections."
    )

    # Config name
    parser.add_argument(
        '-c', '--configuration',
        type=str,
        default="config",
        help="Specify the name of the config file in the input folder. Useful when switching between multiple config files."
    )

    args = parser.parse_args()

    # --- Step 1: Configure Logging ---
    # The output directory from argparse is passed directly to configure_logging.
    # configure_logging handles creating the directory and setting up file/console handlers.
    try:
        utilities.configure_logging(output_dir=args.output)
    except Exception as e:
        # If logging itself fails, print to stderr and exit
        print(f"CRITICAL ERROR: Failed to configure logging in directory '{args.output}': {e}", file=sys.stderr)
        sys.exit(1)

    logger.info(f"Application starting with arguments: "
                f"input='{args.input}', "
                f"output='{args.output}', "
                f"audio_device_id={args.audio}")

    # --- Step 2: Prepare Database File Path and config file ---
    output_path = Path(args.output)
    db_file_path = output_path / (args.database + ".db")

    logger.info(f"Database file path will be: {db_file_path}")

    # Now let's configure
    if args.input:
        input_path = Path(args.input)
        config_path = input_path / (args.configuration + ".json")
    else:
        # Default to looking for config in the current working directory's config folder
        config_path = Path.cwd() / "config" / (args.configuration + ".json")
        logger.info(f"No input directory specified (-i). Looking for config at: {config_path}")

    config = utilities.get_config(config_path)

    logger.info(f"System is configured as follows \n {config}")

    # --- Step 3: Instantiate and Run BirdListener ---
    listener = None
    try:
        listener = BirdListener(
            db_file=str(db_file_path),
            config=config,
            audio_input_device=args.audio,
        )

        logger.info("BirdListener initialized. Starting application threads...")
        listener.run()

        # --- Step 4: Keep Main Thread Alive and Handle User Input ---
        logger.info("BirdListener is running. Press Ctrl+C to stop.")
        while listener._running:  # Continue as long as the listener's internal flag is True
            try:
                # Provide a clear prompt for the user
                user_input = input("Enter 'status' for queue info, or Ctrl+C to stop: ").strip().lower()
                if user_input == 'status':
                    # Safely check queue sizes (they are thread-safe)
                    audio_q_size = listener._audio_chunk_queue.qsize()
                    db_q_size = listener._db_write_queue.qsize()
                    logger.info(f"Current queue sizes: Audio={audio_q_size}, DB Write={db_q_size}")

            except KeyboardInterrupt:
                logger.info("Ctrl+C detected. Initiating graceful shutdown...")
                break
            except EOFError:
                logger.info("EOF detected. Initiating graceful shutdown...")
                break
            except Exception as e:
                logger.error(f"Error during main loop user input handling: {e}", exc_info=True)
                time.sleep(1)  # Small pause to prevent busy-looping on errors

    except Exception as e:
        # Catch any unhandled exceptions from listener.run() or its threads
        logger.critical(f"An unhandled critical error occurred during BirdListener runtime: {e}", exc_info=True)
        sys.exit(1)  # Exit with an error code to indicate failure
    finally:
        # --- Step 5: Ensure Graceful Shutdown ---
        if listener:  # Only try to stop if listener was successfully initialized
            logger.info("Cleaning up BirdListener resources...")
            listener.stop()  # This method handles stopping all internal threads and streams
            logger.info("Application shut down gracefully.")
        else:
            logger.warning("BirdListener was not initialized successfully, skipping shutdown routine.")


if __name__ == "__main__":
    main()