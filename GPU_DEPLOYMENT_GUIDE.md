# GPU Deployment Guide for STT YouTube Server

This guide provides detailed steps for deploying your Faster Whisper-based speech-to-text service on Google Cloud Platform with GPU acceleration.

## Why Use a GPU VM Instead of App Engine?

1. **GPU Acceleration**: Faster Whisper works significantly better with GPU (up to 10-70x faster)
2. **Flexibility**: Full control over your environment and dependencies
3. **Cost Effectiveness**: Pay only for what you use, with the option to stop/start the VM
4. **Reliability**: App Engine has build timeouts and limitations on deployment size

## Prerequisites

1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
2. A GCP project with billing enabled 
3. GPU quota in your preferred region (request if needed)

## Deployment Steps

### 1. Make the Deployment Script Executable

In your local terminal, navigate to the project directory and run:

```bash
# If using Windows:
# Skip this step - run the script with bash from WSL or GitBash

# If using Mac/Linux:
chmod +x deploy_gcp_vm.sh
./deploy_gcp_vm.sh
```

### 2. Connect to the VM

After the script creates your VM, connect to it:

```bash
gcloud compute ssh stt-yt-gpu-server --zone=us-central1-a
```

### 3. Setup GPU Drivers and Docker

On the VM, wait for NVIDIA drivers to install:

```bash
echo 'Waiting for NVIDIA drivers to install...'
while ! command -v nvidia-smi &> /dev/null; do sleep 10; done
nvidia-smi
```

Then install Docker with NVIDIA support:

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### 4. Set Up Your Application

Create a directory and set up application files:

```bash
mkdir -p ~/stt_yt
cd ~/stt_yt
```

Create the Dockerfile:

```bash
cat > Dockerfile << 'EOF'
FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Run the application
CMD ["python", "server.py"]
EOF
```

Create requirements.txt:

```bash
cat > requirements.txt << 'EOF'
flask==2.2.3
faster-whisper==0.9.0
google-api-python-client==2.86.0
torch==2.0.1
yt-dlp==2023.7.6
gunicorn==20.1.0
numpy>=1.24.0
ffmpeg-python>=0.2.0
EOF
```

### 5. Transfer Your Code to the VM

Option 1: Copy from your local machine (run locally):
```bash
gcloud compute scp --recurse /path/to/your/app/* stt-yt-gpu-server:~/stt_yt/ --zone=us-central1-a
```

Option 2: Clone from a Git repository (on the VM):
```bash
git clone YOUR_GIT_REPO_URL .
```

### 6. Build and Run the Docker Container

```bash
sudo docker build -t stt-yt .
sudo docker run -d --gpus all -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=your_api_key \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container stt-yt
```

### 7. Verify Deployment

Check if your container is running:
```bash
sudo docker ps
```

View the logs:
```bash
sudo docker logs -f stt-yt-container
```

### 8. Access Your Server

Access your API at the VM's external IP address:
```bash
echo "http://$(curl -s ifconfig.me)"
```

## Optimization Tips

1. Consider using a small model size to start (e.g., `base`, not `large`)
2. Adjust container memory limits if needed
3. Use CPU throttling with `--cpus` option if cost is a concern
4. Configure auto-shutdown for idle periods to save on VM costs

## Cost Management

1. Stop the VM when not in use:
   ```bash
   gcloud compute instances stop stt-yt-gpu-server --zone=us-central1-a
   ```

2. Start the VM when needed:
   ```bash
   gcloud compute instances start stt-yt-gpu-server --zone=us-central1-a
   ```

3. Consider creating a scheduled stop/start using Cloud Scheduler for predictable usage patterns