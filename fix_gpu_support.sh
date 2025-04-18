#!/bin/bash
# Script to fix GPU support for Faster Whisper with proper CUDA/cuDNN installation

echo "=== Setting up GPU support for Faster Whisper ==="

# Stop any existing containers
echo "Stopping existing containers..."
sudo docker stop stt-yt-container-new || true
sudo docker rm stt-yt-container-new || true

# Create proper GPU-enabled Dockerfile
echo "Creating Dockerfile with proper CUDA/cuDNN support..."
cat > Dockerfile.gpu << 'EOF'
FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install requirements with pinned versions
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# Make nvidia-smi available in the container for debugging
COPY --from=nvidia/cuda:11.7.1-base-ubuntu20.04 /usr/bin/nvidia-smi /usr/bin/nvidia-smi

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Export CUDA paths to help library discovery
ENV PATH=/usr/local/nvidia/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}
# Explicitly use CTC-decoder in CPU mode to avoid libcudnn_cnn_infer.so issues
ENV CUDA_VISIBLE_DEVICES=0
ENV CT2_VERBOSE=1

# Run the application
CMD ["python", "server.py"]
EOF

# Create requirements.txt file
echo "Creating requirements.txt with compatible versions..."
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
ctranslate2==3.15.1
EOF

# Create a script to verify GPU visibility from Python
echo "Creating GPU verification script..."
cat > verify_gpu.py << 'EOF'
import torch
import sys

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda if torch.cuda.is_available() else 'N/A'}")
print(f"Number of CUDA devices: {torch.cuda.device_count()}")

if torch.cuda.is_available() and torch.cuda.device_count() > 0:
    device = torch.device("cuda:0")
    print(f"Current CUDA device: {torch.cuda.current_device()}")
    print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
    print("\nGPU is properly configured!")
    sys.exit(0)
else:
    print("\nNo CUDA GPU detected. There might be an issue with the drivers or installation.")
    sys.exit(1)
EOF

# Build and run the GPU-enabled Docker image
echo "Building GPU-enabled Docker image..."
sudo docker build -t stt-yt-gpu -f Dockerfile.gpu .

echo "Verifying GPU support in the container..."
sudo docker run --rm --gpus all stt-yt-gpu python verify_gpu.py

echo "Starting new container with proper GPU support..."
sudo docker run -d --gpus all -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container-gpu stt-yt-gpu

echo ""
echo "===== GPU Support Setup Complete ====="
echo "Check the container status:"
sudo docker ps | grep stt-yt-container-gpu
echo ""
echo "Check logs with:"
echo "sudo docker logs -f stt-yt-container-gpu"
echo ""
echo "To test if the server is working, visit:"
echo "http://$(curl -s ifconfig.me)"