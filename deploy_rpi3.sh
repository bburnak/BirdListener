#!/bin/bash
# deploy_rpi3.sh — Deploy BirdListener to a Raspberry Pi 3 over SSH
# Usage: bash deploy_rpi3.sh [user@host] [remote_dir]
#   e.g. bash deploy_rpi3.sh baris@pi3b2.local ~/birdlistener

set -e

REMOTE="${1:-baris@pi3b2.local}"
REMOTE_DIR="${2:-~/birdlistener}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying BirdListener to $REMOTE:$REMOTE_DIR ==="

# 1. Sync project files (exclude unnecessary stuff)
echo "[1/4] Syncing project files..."
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'venv/' \
    --exclude '.git/' \
    --exclude 'data/' \
    --exclude '*.db' \
    --exclude '*.log' \
    "$SCRIPT_DIR/" "$REMOTE:$REMOTE_DIR/"

# 2. Install system dependencies
echo "[2/4] Installing system dependencies on Pi..."
ssh "$REMOTE" "sudo apt-get update && sudo apt-get install -y --no-install-recommends \
    python3-venv python3-dev \
    libasound2 portaudio19-dev libsndfile1 \
    libatlas-base-dev libopenblas-dev"

# 3. Create venv and install Python deps
echo "[3/4] Setting up Python virtual environment..."
ssh "$REMOTE" "cd $REMOTE_DIR && \
    python3 -m venv venv && \
    . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements_rpi3.txt"

# 4. Print next steps
echo ""
echo "=== Deployment complete! ==="
echo ""
echo "To run on the Pi:"
echo "  ssh $REMOTE"
echo "  cd $REMOTE_DIR"
echo "  source venv/bin/activate"
echo "  python -m sounddevice                    # find your mic device ID"
echo "  python main.py -c config_low_memory -o ./data"
echo "  python main.py -c config_low_memory -o ./data -a <DEVICE_ID>  # if not default"
echo ""
echo "To monitor memory:"
echo "  ssh $REMOTE 'free -h'"
echo "  ssh $REMOTE 'htop'"
