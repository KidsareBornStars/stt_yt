#!/bin/bash
# Script to fix CUDA and cuDNN libraries for Faster Whisper

echo "=== Installing CUDA and cuDNN Libraries for Faster Whisper ==="

# Update package lists
echo "Updating package lists..."
sudo apt-get update

# Install necessary dependencies
echo "Installing dependencies..."
sudo apt-get install -y build-essential wget

# Install libcudnn8 package
echo "Installing cuDNN libraries..."
sudo apt-get install -y libcudnn8 libcudnn8-dev

# Create a script to fix the Docker container
echo "Creating fix script for Docker container..."
cat > fix_container.sh << 'EOF'
#!/bin/bash
# Fix CUDA libraries in Docker container

# Stop the container
sudo docker stop stt-yt-container-new

# Create a Dockerfile for the updated image
cat > Dockerfile.cudnn << 'EOD'
FROM stt-yt

# Install cuDNN runtime libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libcudnn8 \
        libcudnn8-dev && \
    rm -rf /var/lib/apt/lists/*

# Set LD_LIBRARY_PATH to include CUDA libraries
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

CMD ["python", "server.py"]
EOD

# Build the new image with cuDNN support
sudo docker build -t stt-yt:cudnn -f Dockerfile.cudnn .

# Start a new container with the updated image
sudo docker run -d --gpus all -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container-fixed stt-yt:cudnn

echo "New container started with cuDNN libraries"
echo "Check logs with: sudo docker logs -f stt-yt-container-fixed"
EOF

chmod +x fix_container.sh

# Create a fallback script for CPU-only mode
echo "Creating CPU fallback script..."
cat > use_cpu_mode.sh << 'EOF'
#!/bin/bash
# Switch to CPU-only mode for Faster Whisper

# Stop existing container
sudo docker stop stt-yt-container-new || true
sudo docker stop stt-yt-container-fixed || true

# Create a temporary file to modify server.py
cat > server_cpu.py << 'EOD'
import os
import warnings
import io
import torch
from flask import Flask, request, jsonify, send_file
from faster_whisper import WhisperModel
from googleapiclient.discovery import build
import yt_dlp
import re
import traceback

# Environment variables - use environment variables from cloud service
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', 'AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8')
PORT = int(os.environ.get('PORT', 8000))
ENV = os.environ.get('FLASK_ENV', 'production')

# Suppress warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)

# Global Whisper model initialization - FORCE CPU
print("Initializing Whisper model in CPU mode...")
model = WhisperModel("medium", device="cpu")
print(f"Using device: cpu (forced)")

# Rest of server.py below...
EOD

# Update the Docker image to use CPU
cat > Dockerfile.cpu << 'EOD'
FROM stt-yt

# Copy the modified server file
COPY server_cpu.py /app/server.py

CMD ["python", "server.py"]
EOD

# Build CPU-only image
sudo docker build -t stt-yt:cpu -f Dockerfile.cpu .

# Run container with CPU-only mode
sudo docker run -d -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container-cpu stt-yt:cpu

echo "CPU-only container started"
echo "Note: Speech recognition will be slower but should work without GPU/CUDA errors"
echo "Check logs with: sudo docker logs -f stt-yt-container-cpu"
EOF

chmod +x use_cpu_mode.sh

echo "====== Instructions ======"
echo "Two options to fix the CUDA library issues:"
echo ""
echo "Option 1: Fix cuDNN in container (RECOMMENDED)"
echo "Run this command on your VM:"
echo "./fix_container.sh"
echo ""
echo "Option 2: Switch to CPU-only mode (SLOWER but MORE RELIABLE)"
echo "Run this command on your VM:"
echo "./use_cpu_mode.sh"
echo ""
echo "To execute these scripts on your VM, use:"
echo "gcloud compute ssh stt-yt-gpu --zone=asia-northeast3-c --command=\"cd ~/stt_yt && ./fix_container.sh\""
echo "or"
echo "gcloud compute ssh stt-yt-gpu --zone=asia-northeast3-c --command=\"cd ~/stt_yt && ./use_cpu_mode.sh\""