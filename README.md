# BirdListener

BirdListener is a Python project for detecting and logging bird species from audio data. It is designed to process audio chunks, identify bird species, and store detection results in a structured format. The project is modular, with clear separation between detection logic, database handling, and utility functions.

## Features
- Detects bird species from audio data
- Logs detections with timestamp, confidence, and chunk interval
- Modular codebase for easy extension
- Unit and integration tests
- Docker support for deployment

## Project Structure
```
birdcode/           # Main package with detection, database, and utility modules
config/             # Configuration files (e.g., config.json)
tests/              # Unit and integration tests
Dockerfile          # Docker container definition
docker-compose.yml  # Docker Compose setup
requirements.txt    # Python dependencies
main.py             # Entry point for running the application
```

## Installation
1. Clone the repository:
   ```sh
   git clone <repo-url>
   cd BirdListener
   ```
2. (Optional) Create and activate a virtual environment:
   ```sh
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage
To run the main application:
```sh
python main.py
```

To run tests:
```sh
pytest
```

## Docker
To build and run the project using Docker:
```sh
docker-compose up --build
```

## Configuration
Edit `config/config.json` to adjust detection parameters and other settings.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](LICENSE)
