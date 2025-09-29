# BirdListener

BirdListener is a real-time bird species detection system that continuously monitors audio input from a microphone, identifies bird species using machine learning, and logs detections with timestamps and confidence scores to a SQLite database.

## What It Does

This application listens to audio in real-time, processes it in chunks (default 300 seconds), and uses the BirdNET machine learning model to identify bird species. When a bird is detected with sufficient confidence (default 70%), the detection is logged with:
- Species name
- Confidence score (0.0 to 1.0)
- Timestamp (UTC)
- Audio chunk interval where the bird was detected

The system is designed to run continuously and can operate on resource-constrained devices like Raspberry Pi.

## Why This Project

The project started with a sudden interest in hearing all kinds of bird songs all day while working at my front porch. Besides my fascination with birds, personal goals included:
- Creating fully containerized software that can operate on third-party hardware (Raspberry Pi)
- Learning VS Code (coming from PyCharm background)
- Building a modular, well-tested Python application

## Features

- **Real-time audio processing**: Continuous monitoring with configurable audio parameters
- **BirdNET integration**: Uses pre-trained neural networks for accurate species identification  
- **Threaded architecture**: Separate threads for audio capture, processing, and database writing
- **SQLite logging**: Persistent storage of detections with batch writing for performance
- **Configurable thresholds**: Adjustable confidence levels and audio parameters
- **Docker support**: Containerized deployment with audio device access
- **Comprehensive testing**: Unit tests for all major components
- **Graceful shutdown**: Proper cleanup of resources and pending operations

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Audio Input    │───▶│  BirdListener   │───▶│  Database       │
│  (Microphone)   │    │  Processing     │    │  Writer         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  BirdNET        │
                       │  ML Model       │
                       └─────────────────┘
```

## Project Structure

```
birdcode/                 # Main Python package
├── __init__.py
├── birdlistener.py      # Core BirdListener class with audio processing
├── database.py          # DatabaseWriter for threaded SQLite operations  
├── detection.py         # BirdDetection data class
└── utilities.py         # Logging and configuration utilities

config/
└── config.json          # Audio and detection parameters

tests/
├── unit/                # Unit tests for all modules
├── integration/         # Integration tests (if any)
└── ...

main.py                  # CLI entry point with argument parsing
requirements.txt         # Python dependencies including BirdNET
Dockerfile              # Container definition with audio support
docker-compose.yml      # Docker setup with device access
pytest.ini              # Test configuration
```

## Installation

**Note**: BirdNET requires Python 3.9-3.11. Python 3.12+ is not currently supported.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/bburnak/BirdListener.git
   cd BirdListener
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify audio devices** (optional):
   ```bash
   python -m sounddevice
   ```

## Usage

### Basic Usage
Run with default settings (uses default audio device, saves to current directory):
```bash
python main.py
```

### Advanced Usage
```bash
python main.py -a 0 -o ./output -d bird_detections -c config
```

**Arguments**:
- `-a, --audio`: Audio input device ID (use `python -m sounddevice` to list)
- `-o, --output`: Output directory for logs and database (default: current directory)  
- `-d, --database`: Database filename without extension (default: "bird_detections")
- `-c, --configuration`: Config filename without extension (default: "config")
- `-i, --input`: Input directory for config file (default: current directory)

### Interactive Commands
While running, you can:
- Type `status` to see queue sizes
- Press `Ctrl+C` to gracefully shutdown

### Example Output
```
2025-01-01 10:15:23 [INFO] BirdListener: Starting BirdListener application components...
2025-01-01 10:15:24 [INFO] BirdListener: Predicted 'American Robin' with confidence 0.87
2025-01-01 10:18:45 [INFO] BirdListener: Predicted 'Northern Cardinal' with confidence 0.92
```

## Configuration

Edit `config/config.json` to adjust parameters:

```json
{
  "sample_rate": 44100,        // Audio sample rate in Hz
  "channels": 1,               // Mono audio
  "blocksize": 1024,          // Audio buffer size
  "chunk_seconds": 300,        // Process audio in 5-minute chunks
  "detection_threshold": 0.7   // Minimum confidence to log detection
}
```

## Docker Deployment

For deployment on devices like Raspberry Pi:

1. **Build the image**:
   ```bash
   docker build -t bird-listener .
   ```

2. **Run with audio device access**:
   ```bash
   docker-compose up --build
   ```

The Docker setup automatically mounts `/dev/snd` for audio device access.

## Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=birdcode
```

## Database Schema

Detections are stored in SQLite with this schema:
```sql
CREATE TABLE detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    chunk_start_sec REAL NOT NULL,
    chunk_end_sec REAL NOT NULL,
    species TEXT NOT NULL,
    confidence REAL NOT NULL
);
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

Please ensure:
- Tests pass (`pytest`)
- Code follows existing style
- New features include tests

## License

[MIT](LICENSE)
