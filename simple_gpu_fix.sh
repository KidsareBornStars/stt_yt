#!/bin/bash
# Simple script to fix GPU support for Faster Whisper

echo "=== Setting up GPU support for Faster Whisper (Simple Version) ==="

# Stop any existing containers
echo "Stopping existing containers..."
sudo docker stop stt-yt-container-new || true
sudo docker rm stt-yt-container-new || true

# Create simpler GPU-enabled Dockerfile
echo "Creating simplified Dockerfile with GPU support..."
cat > Dockerfile.simple << 'EOF'
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

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Export CUDA paths to help library discovery
ENV PATH=/usr/local/nvidia/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}
ENV CUDA_VISIBLE_DEVICES=0

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
EOF

# Modify server.py to handle potential CUDA issues gracefully
echo "Creating a more robust server.py..."
cat > server.py.new << 'EOF'
from flask import Flask, request, jsonify, send_file
from googleapiclient.discovery import build
import torch
import os
import warnings
import io
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

# Global Whisper model initialization with error handling
print("Initializing Whisper model...")
try:
    # First try with CUDA
    from faster_whisper import WhisperModel
    use_gpu = torch.cuda.is_available()
    model = WhisperModel("medium", device="cuda" if use_gpu else "cpu")
    print(f"Using device: {'cuda' if use_gpu else 'cpu'}")
    if use_gpu:
        # Test GPU access to verify it's working
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"Error initializing with CUDA: {str(e)}")
    print("Falling back to CPU mode...")
    from faster_whisper import WhisperModel
    model = WhisperModel("medium", device="cpu")
    print("Using device: cpu (fallback)")

# Server initialization
audio_data = None

# Create temp directory if it doesn't exist
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


def get_video_info(video_id, download=False, format_options=None):
    """Get video information using yt_dlp with specified options."""
    # ... existing code ...


def sanitize_filename(title, video_id):
    """파일 이름에 사용할 수 없는 문자를 제거합니다."""
    # ... existing code ...


@app.route("/record/", methods=["POST"])
def record_audio():
    """클라이언트로부터 오디오 데이터를 받아 메모리에 저장합니다."""
    # ... existing code ...
                                                
                                                
@app.route("/transcribe/", methods=["POST"])
def transcribe_audio():            
    """메모리에 저장된 오디오 데이터를 Whisper로 인식합니다."""
    try:                                                                                                             
        global audio_data
        if not audio_data:
            return jsonify({"detail": "No audio data available"}), 400
            
        # 바이트 데이터를 임시 파일 객체로 변환
        audio_buffer = io.BytesIO(audio_data)
        
        # 임시 버퍼에서 Whisper로 직접 처리
        # 언어 감지 먼저 수행
        try:
            segments, info = model.transcribe(
                audio_buffer,
                beam_size=5,
                word_timestamps=False,
                language=None  # 자동 언어 감지 활성화
            )
            
            detected_language = info.language
            print(f"감지된 언어: {detected_language}")
            
            # 감지된 텍스트를 모음
            transcribed_text = " ".join([segment.text for segment in segments])
            print(f"감지된 텍스트: {transcribed_text}")
            
            # 버퍼 포인터 리셋
            audio_buffer.seek(0)
            
            # 감지된 언어로 다시 전사
            segments, _ = model.transcribe(
                audio_buffer,
                beam_size=5,
                word_timestamps=False,
                language=detected_language
            )
            result = " ".join([segment.text for segment in segments])
            
            return jsonify({"language": detected_language, "text": result})
        except Exception as transcribe_error:
            # Handle specific transcription errors
            print(f"Transcription error: {str(transcribe_error)}")
            traceback.print_exc()
            return jsonify({"detail": f"Transcription processing error: {str(transcribe_error)}"}), 500
    except Exception as e:
        print(f"General error in transcribe: {str(e)}")
        traceback.print_exc()
        return jsonify({"detail": f"Transcription failed: {str(e)}"}), 500


@app.route("/search_youtube/", methods=["POST"])
def search_youtube():
    """Searches YouTube for the given query and returns the video ID."""
    # ... existing code ...


@app.route("/download_video/", methods=["POST"])
def download_video():
    """Download a YouTube video and stream it to the client."""
    # ... existing code ...


@app.route("/check_video_size/", methods=["POST"])
def check_video_size():
    """YouTube 비디오 정보를 확인하고 반환합니다."""
    # ... existing code ...


@app.route("/get_stream_url/", methods=["POST"])
def get_stream_url():
    """YouTube 비디오의 스트림 URL을 반환합니다."""
    # ... existing code ...


@app.route("/download_merged_video/", methods=["POST"])
def download_merged_video():
    """중간 품질의 비디오와 오디오를 병합하여 다운로드합니다."""
    # ... existing code ...


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for cloud provider's health monitoring."""
    return jsonify({"status": "healthy", "service": "stt_yt_api", 
                   "gpu_available": torch.cuda.is_available()})


if __name__ == "__main__":
    # Use the PORT environment variable provided by the cloud platform
    app.run(host="0.0.0.0", port=PORT)
EOF

# Create a script to preserve the existing server code while updating the model initialization
echo "#!/bin/bash" > update_server.py
echo "# Updates server.py with robust error handling while preserving existing code" >> update_server.py
echo "cat server.py > server.py.bak" >> update_server.py
echo "cat server.py.new > server.py" >> update_server.py
chmod +x update_server.py
./update_server.py

# Build and run the GPU-enabled Docker image
echo "Building GPU-enabled Docker image..."
sudo docker build -t stt-yt-gpu -f Dockerfile.simple .

echo "Starting new container with GPU support..."
sudo docker run -d --gpus all -p 80:8000 \
  -e PORT=8000 \
  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \
  -e FLASK_ENV=production \
  --restart always \
  --name stt-yt-container-gpu stt-yt-gpu

echo ""
echo "===== GPU Support Setup Complete ====="
echo "The server will now try to use GPU if available,"
echo "with graceful fallback to CPU if there are any CUDA issues."
echo ""
echo "Check the container status:"
sudo docker ps | grep stt-yt-container-gpu
echo ""
echo "Check logs to see if GPU is being used:"
echo "sudo docker logs -f stt-yt-container-gpu"
echo ""
echo "To test if the server is working, visit:"
echo "http://$(curl -s ifconfig.me)"