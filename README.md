# STT YouTube Search Server

A Flask server that handles speech-to-text transcription and YouTube video search/streaming.

## Overview

This application provides the following functionality:
- Speech recognition using the Faster Whisper model
- YouTube search integration
- Video streaming and downloading

## Deployment on Google Cloud Platform

### Prerequisites

1. [Create a Google Cloud account](https://cloud.google.com/) if you don't have one
2. [Install Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
3. [Set up a Google Cloud Project](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
4. [Enable billing for your project](https://cloud.google.com/billing/docs/how-to/modify-project)
5. Enable required APIs:
   - Cloud Build API
   - Cloud Run API (if using Cloud Run)
   - App Engine API (if using App Engine)
   - Compute Engine API
   - GPU quota request (see GPU section below)

### GPU Setup for Faster Whisper

For optimal performance with Faster Whisper, you'll need GPU acceleration:

1. Request GPU quota in your GCP project:
   - Go to IAM & Admin > Quotas
   - Search for "NVIDIA T4 GPUs" or "NVIDIA L4 GPUs"
   - Select the quota and click "EDIT QUOTAS"
   - Request an increase (at least 1 GPU in your preferred region)
   - Provide business justification and submit
   - Approval may take 24-48 hours

2. Check available GPU types and zones:
   ```
   gcloud compute accelerator-types list
   ```

### Option 1: Deploy to Google App Engine

*Note: App Engine Standard does not support GPUs. Consider Cloud Run or Compute Engine for GPU support.*

1. Initialize the Google Cloud SDK:
   ```
   gcloud init
   ```

2. Select or create a project:
   ```
   gcloud config set project YOUR_PROJECT_ID
   ```

3. Deploy to App Engine:
   ```
   gcloud app deploy app.yaml
   ```

4. View the deployed app:
   ```
   gcloud app browse
   ```

### Option 2: Deploy to Cloud Run using Docker

*Note: Cloud Run now supports GPUs in preview with limitations. See [Cloud Run GPU documentation](https://cloud.google.com/run/docs/using-gpus).*

1. Build and push Docker image to Google Container Registry:
   ```
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stt-yt
   ```

2. Deploy to Cloud Run with GPU:
   ```
   gcloud run deploy stt-yt \
     --image gcr.io/YOUR_PROJECT_ID/stt-yt \
     --platform managed \
     --allow-unauthenticated \
     --cpu 4 \
     --memory 16Gi \
     --gpu 1 \
     --gpu-type=nvidia-t4 \
     --region=us-central1
   ```

### Option 3: Deploy to GCP VM Instance with GPU (Recommended)

1. Create a Compute Engine VM instance with GPU:
   ```
   gcloud compute instances create stt-yt-server \
     --image-family=debian-11 \
     --image-project=debian-cloud \
     --machine-type=n1-standard-4 \
     --boot-disk-size=30GB \
     --accelerator=type=nvidia-tesla-t4,count=1 \
     --maintenance-policy=TERMINATE \
     --metadata="install-nvidia-driver=True" \
     --zone=us-central1-a
   ```

2. SSH into the instance:
   ```
   gcloud compute ssh stt-yt-server
   ```

3. Install Docker with NVIDIA support:
   ```
   # Install basic utilities
   sudo apt-get update
   sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

   # Add Docker repository
   curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
   echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   
   # Install Docker
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io

   # Install NVIDIA Container Toolkit
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update
   sudo apt-get install -y nvidia-docker2
   
   # Restart Docker
   sudo systemctl restart docker
   ```

4. Clone your repository or upload your files to the VM

5. Create a Dockerfile for GPU support:
   ```
   # Create Dockerfile
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
   
   # Run the application
   CMD ["python", "server.py"]
   EOF
   ```

6. Create requirements.txt:
   ```
   echo "flask
   faster-whisper
   google-api-python-client
   torch
   yt-dlp" > requirements.txt
   ```

7. Build and run the Docker container with GPU support:
   ```
   sudo docker build -t stt-yt .
   sudo docker run -d --gpus all -p 80:8000 \
     -e PORT=8000 \
     -e YOUTUBE_API_KEY=your_api_key \
     -e FLASK_ENV=production \
     --name stt-yt-container stt-yt
   ```

8. (Optional) Set up automatic restart on VM reboot:
   ```
   sudo systemctl enable docker
   echo '#!/bin/bash
   docker start stt-yt-container' | sudo tee /etc/rc.local
   sudo chmod +x /etc/rc.local
   ```

9. (Optional) Set up a domain name and SSL with Nginx

## Environment Variables

Configure these environment variables in your deployment:

- `YOUTUBE_API_KEY`: Your YouTube API key
- `PORT`: Port to run the server on (default: 8080)
- `FLASK_ENV`: Environment to run Flask in (development/production)

## API Endpoints

- `POST /record/`: Receive audio data
- `POST /transcribe/`: Transcribe recorded audio
- `POST /search_youtube/`: Search YouTube with text query
- `POST /download_video/`: Download a YouTube video
- `GET /`: Health check endpoint

## Client Integration

Update the BASE_URL in your client code (app.py) to point to your deployed server URL.

## Note about Compute Resources

The speech recognition model (Whisper) requires significant memory and CPU resources. Make sure to select an appropriate instance size with at least 2GB of RAM.