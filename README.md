# BirdListener

BirdListener is a Python application that uses [BirdNET](https://github.com/kahst/BirdNET-Analyzer) to detect and log bird species from real-time audio input. It captures audio from a microphone, analyzes it in chunks using BirdNET's neural network, and stores detections in a SQLite database. Designed to run headless on a **Raspberry Pi** (or any Linux system with a USB microphone).

## Features

- **Real-time audio capture** via PortAudio/ALSA (USB microphone supported)
- **BirdNET species identification** with configurable confidence threshold
- **SQLite database** for persistent detection logging (species, confidence, timestamp)
- **Threaded architecture** — audio capture, analysis, and database writing run concurrently
- **Docker support** for containerized deployment on Raspberry Pi
- **Configurable** sample rate, chunk size, detection threshold via JSON config

## Hardware Requirements

- **Raspberry Pi 4 or 5** (4 GB+ RAM required — peak application memory is ~1.5–2 GB with full TensorFlow + audio buffering)
- USB microphone or USB sound card with microphone input
- SD card (32 GB+) or external storage for database and Docker image
- **8 GB RAM recommended** if running other services alongside BirdListener
- Raspberry Pi 3 (1 GB) **can work** with a low-memory configuration (see [Tuning for Low-Memory Devices](#tuning-for-low-memory-devices) below)

## Project Structure

```
main.py                 # Entry point — CLI argument parsing and application lifecycle
birdcode/
    birdlistener.py     # Core class: audio capture, BirdNET analysis, detection queuing
    database.py         # Threaded SQLite writer with batch buffering
    detection.py        # BirdDetection data class
    utilities.py        # Logging setup and config file loading
config/
    config.json         # Runtime configuration (sample rate, chunk size, threshold)
tests/
    unit/               # Unit tests (pytest)
    integration/        # Integration tests (placeholder)
Dockerfile              # Container image definition
docker-compose.yml      # Docker Compose for Raspberry Pi deployment
requirements.txt        # Python dependencies
```

## Installation

### Prerequisites (Raspberry Pi / Linux)

Install system-level audio dependencies:

```sh
sudo apt-get update
sudo apt-get install -y libasound2 portaudio19-dev libsndfile1
```

### Python Setup

```sh
git clone https://github.com/bburnak/BirdListener.git
cd BirdListener
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Install test dependencies (Optional)
If you are interested in developing BirdListener, make sure you can run the tests.
```sh
pip install pytest
```

## Usage

### Command-Line Arguments

```
python main.py [OPTIONS]

Options:
  -i, --input DIR        Directory containing config file(s). If omitted,
                         defaults to ./config/ in the current working directory.
  -o, --output DIR       Base directory for logs and database file (default: .)
  -a, --audio ID         Audio input device ID. Use `python -m sounddevice`
                         to list available devices.
  -d, --database NAME    Database filename (without .db extension, default: bird_detections)
  -c, --configuration NAME  Config filename (without .json extension, default: config)
```

### Examples

```sh
# Run with defaults (config from ./config/config.json, output to current dir)
python main.py

# Specify config directory and output location
python main.py -i ./config -o ./data

# Use a specific audio device (list devices first)
python -m sounddevice
python main.py -a 2 -o ./data
```

### Running Tests

```sh
pytest tests/unit
```

## Configuration

Edit `config/config.json` to adjust runtime parameters:

```json
{
  "sample_rate": 44100,
  "channels": 1,
  "blocksize": 1024,
  "chunk_seconds": 300,
  "detection_threshold": 0.7
}
```

| Parameter              | Description                                                    | Default  |
|------------------------|----------------------------------------------------------------|----------|
| `sample_rate`          | Audio sample rate in Hz  | 44100    |
| `channels`             | Number of audio channels (1 = mono)                            | 1        |
| `blocksize`            | Audio buffer block size in samples                             | 1024     |
| `chunk_seconds`        | Duration of each audio chunk sent to BirdNET for analysis      | 300      |
| `detection_threshold`  | Minimum confidence score (0.0–1.0) to log a detection          | 0.7      |
| `model_backend`        | BirdNET model backend: `"tf"` (TFLite/CPU) or `"pb"` (ProtoBuf/CPU+GPU) | `"tf"` |

## Tuning for Low-Memory Devices

BirdListener can run on devices with as little as **1 GB RAM** (e.g., Raspberry Pi 3) with the right configuration. The two main memory consumers are the **audio buffer** and **TensorFlow**. Even with this configuration, it is likely that some of the buffered audio samples will get lost before being analyzed by BirdNET.

### Memory Impact of Configuration Parameters

| Parameter        | Effect on Memory | Effect on Performance | Recommendation |
|------------------|------------------|-----------------------|----------------|
| `chunk_seconds`  | Buffer = `chunk_seconds × sample_rate × 4 bytes`. 300s @ 48kHz = ~55 MB | **Keep high.** Each `model.predict()` call has fixed model overhead. A 300s chunk batches ~100 BirdNET windows per call; a 30s chunk only ~10 — making overhead dominate on slow CPUs. | Keep at 300 |
| `sample_rate`    | Lower rate = proportionally smaller buffer and temp WAV files | BirdNET resamples to 48kHz internally, so slight extra CPU for resampling. Negligible on Pi 4+, noticeable on Pi 3. | 16000 for low-mem, but also check with your microphone's specs |
| `blocksize`      | Minimal memory impact | Lower = more responsive callbacks but slightly higher CPU interrupt frequency | 512 for low-mem |

### Why `chunk_seconds` Should Stay at 300

BirdNET analyzes audio in fixed **3-second windows** regardless of chunk size. The chunk size determines how many windows are processed per model invocation:

| `chunk_seconds` | Windows per call | Overhead ratio | Analysis frequency |
|-----------------|-----------------|-------------------|-------------------|
| 300             | ~100            | Low — overhead amortized over 100 inferences | Every 5 min |
| 60              | ~20             | Medium            | Every 1 min |
| 30              | ~10             | **High — model startup/teardown dominates** | Every 30 sec |

On a Raspberry Pi 3's limited CPU, the fixed overhead per model call is significant. Keeping `chunk_seconds` at 300 ensures the CPU spends most of its time on actual inference rather than repeated setup. Detection quality per window is identical regardless of chunk size.

### Low-Memory Configuration (Raspberry Pi 3 / 1 GB)

A pre-made low-memory config is included at `config/config_low_memory.json`:

```json
{
  "sample_rate": 16000,
  "channels": 1,
  "blocksize": 512,
  "chunk_seconds": 300,
  "detection_threshold": 0.7
}
```

Use it with:

```sh
python main.py -c config_low_memory -o ./data
```

**What changes and why:**

- **`sample_rate`: 48000 → 16000** — Reduces audio buffer from ~55 MB to ~18 MB, and temp WAV files proportionally. BirdNET resamples to 48kHz during analysis, so there is a small CPU cost for resampling, but it significantly reduces memory.
- **`blocksize`: 1024 → 512** — Reduces per-callback processing; helps with responsiveness on slower CPUs.
- **`chunk_seconds`: stays at 300** — Keeps TensorFlow overhead amortized. The ~18 MB buffer (at 16kHz) is negligible compared to TF's ~300–500 MB footprint.

### Estimated Memory Usage by Config

| Config                    | Audio Buffer | TensorFlow  | Total (est.) | Target device    |
|---------------------------|-------------|-------------|--------------|------------------|
| Default (300s / 48kHz)    | ~55 MB      | ~300–500 MB | ~600–800 MB  | RPi 4/5 (4 GB+) |
| Low-mem (300s / 16kHz)    | ~18 MB      | ~300–500 MB | ~550–750 MB  | RPi 4 (2 GB)    |
| Low-mem + tflite-runtime  | ~18 MB      | ~50–100 MB  | ~250–400 MB  | RPi 3 (1 GB)    |

### Using tflite-runtime Instead of Full TensorFlow

For the lowest memory footprint (required for Raspberry Pi 3), replace `tensorflow` with `tflite-runtime`:

```sh
pip uninstall tensorflow
pip install tflite-runtime
```

This reduces TensorFlow's memory footprint from ~300–500 MB to ~50–100 MB, making BirdListener viable on 1 GB devices. The `birdnet` library uses `tflite-runtime` as a backend when loaded with `model_backend: "tflite"` (the default).

> **Tip:** Combine the low-memory config with `tflite-runtime` for the best results on constrained hardware. Monitor memory usage with `htop` or `free -h` during operation.
> Reducing `chunk_seconds` is a last resort — only do it if you're still OOM after switching to `tflite-runtime`.

## Docker Deployment (Raspberry Pi)

### Build and Run

```sh
docker compose up --build -d
```

This will:
1. Build the container image from the Dockerfile
2. Mount `./config` (read-only) for configuration
3. Mount `./data` for persistent database and log storage
4. Pass through `/dev/snd` for microphone access

### View Logs

```sh
docker compose logs -f bird-listener
```

### Stop

```sh
docker compose down
```

### Notes for Raspberry Pi Docker

- The container needs access to `/dev/snd` for the microphone. The `docker-compose.yml` maps this device and adds the `audio` group.
- If you encounter permission issues with the microphone, you may need to add `privileged: true` to the service in `docker-compose.yml`.
- Data (database + logs) is persisted in the `./data` volume mount. For SD card longevity, consider pointing this to an external USB drive or NAS mount.

## SD Card Longevity Tips

- Mount an external USB drive or NAS share for the database and logs to reduce SD card writes.
- Consider using `tmpfs` for temporary WAV files (BirdListener writes temp chunks during analysis).
- Use a high-endurance SD card rated for continuous write workloads.

## License

[MIT](LICENSE)
