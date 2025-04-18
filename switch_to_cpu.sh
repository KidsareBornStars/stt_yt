#!/bin/bash
# Script to switch Faster Whisper to CPU-only mode

echo "=== Switching to CPU-only mode for Faster Whisper ==="

# Stop any existing containers
echo "Stopping existing containers..."
sudo docker stop stt-yt-container-new || true
sudo docker stop stt-yt-container-fixed || true
sudo docker stop stt-yt-container-cpu || true

# Create a temporary script to modify server.py
echo "Creating CPU-only version of server.py..."
cat > modify_server.py << 'EOF'
#!/usr/bin/env python3
import sys

# Read the original server.py file
with open('server.py', 'r') as f:
    content = f.read()

# Replace the GPU initialization with CPU-only
content = content.replace(
    'model = WhisperModel("medium", device="cuda" if torch.cuda.is_available() else "cpu")',
    'model = WhisperModel("medium", device="cpu")'
)

# Replace the print statement about device
content = content.replace(
    'print(f"Using device: {\'cuda\' if torch.cuda.is_available() else \'cpu\'}")',
    'print("Using device: cpu (forced)")'
)

# Write the modified content back
with open('server.py', 'w') as f:
    f.write(content)

print("Successfully modified server.py to use CPU only")
EOF

# Make the modification script executable
chmod +x modify_server.py

# Create a simple Dockerfile that doesn't install extra packages
echo "Creating simple Dockerfile for CPU mode..."
cat > Dockerfile.cpu << 'EOF'
FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install only essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install requirements with pinned versions
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Run the application
CMD ["python", "server.py"]
EOF

# Create a requirements.txt file
echo "Creating requirements.txt..."
cat > requirements.txt << 'EOF'
flask==2.0.1
werkzeug==2.0.1
faster-whisper==0.9.0
google-api-python-client==2.86.0
torch==2.0.1
yt-dlp==2023.7.6
gunicorn==20.1.0
numpy>=1.24.0
ffmpeg-python>=0.2.0
EOF

# Modify the server.py file to use CPU only
python3 modify_server.py

# Build the CPU-only Docker image
echo "Building Docker image for CPU mode..."
sudo docker build -t stt-yt-cpu -f Dockerfile.cpu .

# Run the container with CPU mode
echo "Starting Docker container in CPU mode..."
sudo docker run -d -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container-cpu stt-yt-cpu

echo ""
echo "===== CPU Mode Setup Complete ====="
echo "Note: Speech recognition will be slower without GPU acceleration,"
echo "but it will work reliably without CUDA/cuDNN errors."
echo ""
echo "Check the container status:"
sudo docker ps | grep stt-yt-container-cpu
echo ""
echo "Check logs with:"
echo "sudo docker logs -f stt-yt-container-cpu"
echo ""
echo "To test if the server is working, visit:"
echo "http://$(curl -s ifconfig.me)"