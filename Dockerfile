FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (libasound2 for sounddevice + portaudio19-dev for PortAudio)
RUN apt-get update && apt-get install -y \
    libasound2 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy source code
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run unit tests (will fail the build if tests fail)
RUN pip install --no-cache-dir pytest \
    && pytest tests/unit

# Default command
ENTRYPOINT ["python", "main.py"]
