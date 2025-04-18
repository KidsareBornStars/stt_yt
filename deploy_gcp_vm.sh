#!/bin/bash
# Deployment script for GCP VM with GPU

# Exit on error
set -e

echo "================================================"
echo "STT YouTube Server - GCP VM Deployment Script"
echo "================================================"

# Default project ID
PROJECT_ID="stt-youtube-446508"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: Google Cloud SDK is not installed. Please install it first."
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "You need to log in to Google Cloud first."
    gcloud auth login
fi

# Set the project
echo "Using project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Check GPU quota
echo "Checking GPU quota... (This may take a moment)"
echo "Note: If you don't have GPU quota, please request it in Google Cloud Console"
echo "IAM & Admin > Quotas & system limits > Filter for 'NVIDIA T4 GPUs'"

# Create VM with GPU
VM_NAME="stt-yt-gpu-server"
ZONE="us-central1-a"
MACHINE_TYPE="n1-standard-4"

echo "Creating VM instance with GPU..."
gcloud compute instances create $VM_NAME \
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --machine-type=$MACHINE_TYPE \
    --boot-disk-size=30GB \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --maintenance-policy=TERMINATE \
    --metadata="install-nvidia-driver=True" \
    --zone=$ZONE \
    --tags=http-server,https-server

echo "Creating firewall rules if they don't exist..."
# Check if firewall rule exists before creating
if ! gcloud compute firewall-rules describe allow-http &>/dev/null; then
    gcloud compute firewall-rules create allow-http \
        --allow tcp:80 \
        --target-tags=http-server \
        --description="Allow HTTP traffic" \
        --direction=INGRESS
fi

if ! gcloud compute firewall-rules describe allow-https &>/dev/null; then
    gcloud compute firewall-rules create allow-https \
        --allow tcp:443 \
        --target-tags=https-server \
        --description="Allow HTTPS traffic" \
        --direction=INGRESS
fi

echo "VM instance created! Now connect via SSH:"
echo "gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "After connecting, run the following commands:"
echo "----------------------------------------------"
echo "# Wait for NVIDIA drivers installation to complete (check with nvidia-smi)"
echo "# This may take a few minutes after the VM starts"
echo "echo 'Waiting for NVIDIA drivers to install...'"
echo "while ! command -v nvidia-smi &> /dev/null; do sleep 10; done"
echo "nvidia-smi"
echo ""
echo "# Install Docker and NVIDIA container toolkit"
echo "sudo apt-get update"
echo "sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git"
echo "curl -fsSL https://get.docker.com -o get-docker.sh"
echo "sudo sh get-docker.sh"
echo "distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)"
echo "curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -"
echo "curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
echo "sudo apt-get update"
echo "sudo apt-get install -y nvidia-docker2"
echo "sudo systemctl restart docker"
echo ""
echo "# Create directory for the application"
echo "mkdir -p ~/stt_yt"
echo "cd ~/stt_yt"
echo ""
echo "# Create Dockerfile"
echo "cat > Dockerfile << 'EOF'"
echo "FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime"
echo ""
echo "WORKDIR /app"
echo ""
echo "# Install dependencies"
echo "RUN apt-get update && apt-get install -y --no-install-recommends \\"
echo "    ffmpeg \\"
echo "    git \\"
echo "    && rm -rf /var/lib/apt/lists/*"
echo ""
echo "# Install requirements"
echo "COPY requirements.txt ."
echo "RUN pip install --no-cache-dir -r requirements.txt"
echo ""
echo "# Copy application code"
echo "COPY . ."
echo ""
echo "# Create temp directory"
echo "RUN mkdir -p /app/temp"
echo "RUN chmod 777 /app/temp"
echo ""
echo "# Run the application"
echo "CMD [\"python\", \"server.py\"]"
echo "EOF"
echo ""
echo "# Create requirements.txt"
echo "cat > requirements.txt << 'EOF'"
echo "flask==2.2.3"
echo "faster-whisper==0.9.0"
echo "google-api-python-client==2.86.0"
echo "torch==2.0.1"
echo "yt-dlp==2023.7.6"
echo "gunicorn==20.1.0"
echo "numpy>=1.24.0"
echo "ffmpeg-python>=0.2.0"
echo "EOF"
echo ""
echo "# Copy your application files to the VM"
echo "# Option 1: Copy from local machine (run this locally):"
echo "# gcloud compute scp --recurse /path/to/your/app/* $VM_NAME:~/stt_yt/ --zone=$ZONE"
echo "# Option 2: Clone from git repository:"
echo "# git clone YOUR_GIT_REPO_URL ."
echo ""
echo "# Build and run Docker container"
echo "sudo docker build -t stt-yt ."
echo "sudo docker run -d --gpus all -p 80:8000 \\"
echo "  -e PORT=8000 \\"
echo "  -e YOUTUBE_API_KEY=your_api_key \\"
echo "  -e FLASK_ENV=production \\"
echo "  --restart always \\"
echo "  --name stt-yt-container stt-yt"
echo ""
echo "# Check if container is running"
echo "sudo docker ps"
echo ""
echo "# View logs"
echo "sudo docker logs -f stt-yt-container"
echo ""
echo "# Access your API at: http://$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"