FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (libasound2 for sounddevice + portaudio19-dev for PortAudio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

# Create data directory for database and logs
RUN mkdir -p /app/data

# Default command — config is mounted at /app/config, data goes to /app/data
ENTRYPOINT ["python", "main.py"]
CMD ["-o", "/app/data", "-i", "/app/config"]
