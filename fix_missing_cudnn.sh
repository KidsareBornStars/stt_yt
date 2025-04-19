#!/bin/bash
# Script to fix missing cuDNN libraries for Faster Whisper

echo "=== Fixing Missing cuDNN Libraries for Faster Whisper ==="

# Create a modified version of server.py that handles cuDNN errors
cat > server_modified.py << 'EOF'
from flask import Flask, request, jsonify, send_file, abort
from googleapiclient.discovery import build
import torch
import os
import warnings
import io
import yt_dlp
import re
import traceback
import time
from functools import wraps
from datetime import datetime

# Environment variables
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', 'AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8')
PORT = int(os.environ.get('PORT', 8000))
ENV = os.environ.get('FLASK_ENV', 'production')

# Security settings
ALLOWED_IPS = os.environ.get('ALLOWED_IPS', '').split(',')
MAX_REQUESTS_PER_MINUTE = 60
RATE_LIMIT_WINDOW = 60  # seconds
ENABLE_RATE_LIMITING = os.environ.get('ENABLE_RATE_LIMITING', 'true').lower() == 'true'

# Suppress warnings
warnings.filterwarnings("ignore")

# Configure to avoid cuDNN issues
os.environ['CT2_CUDA_MEMORY_INITIAL_SIZE'] = '512'  # Smaller initial allocation
os.environ['CT2_CUDA_DYNAMIC_BUFFER'] = '1'  # Dynamic buffer allocation
os.environ['CT2_CUDA_LOG_COMPILATION'] = '0'  # Disable verbose logging
os.environ['CT2_USE_INFERENCE_ENGINES'] = '0'  # Disable inference engines

app = Flask(__name__)

# Request rate limiting
request_history = {}  # IP -> list of timestamps

# Global Whisper model initialization with robust error handling
print("Initializing Whisper model...")
model = None  # Initialize outside to handle exceptions

def init_model():
    global model
    try:
        # First try with CUDA, but with error handling for cuDNN issues
        from faster_whisper import WhisperModel
        if torch.cuda.is_available():
            try:
                # Test with a small model first to check if cuDNN works
                print("Testing GPU setup with small model...")
                temp_model = WhisperModel("tiny", device="cuda")
                del temp_model  # Free up memory
                
                # If it works, load the actual model
                print("GPU test successful, loading medium model...")
                model = WhisperModel("medium", device="cuda")
                print(f"Using device: cuda")
                print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
            except Exception as cuda_error:
                print(f"Error using CUDA: {str(cuda_error)}")
                print("Falling back to CPU mode...")
                model = WhisperModel("medium", device="cpu")
                print("Using device: cpu (GPU failed)")
        else:
            model = WhisperModel("medium", device="cpu")
            print("Using device: cpu (No GPU available)")
    except Exception as e:
        print(f"Error initializing Whisper model: {str(e)}")
        print("Falling back to CPU mode...")
        from faster_whisper import WhisperModel
        model = WhisperModel("medium", device="cpu")
        print("Using device: cpu (fallback)")

# Initialize model
init_model()

# Server initialization
audio_data = None

# Create temp directory if it doesn't exist
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Security middleware
def check_ip_whitelist():
    """Check if the request comes from an allowed IP"""
    if not ALLOWED_IPS or ALLOWED_IPS == ['']:
        return True  # No restriction if no IPs are specified
    
    client_ip = request.remote_addr
    return client_ip in ALLOWED_IPS

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not ENABLE_RATE_LIMITING:
            return f(*args, **kwargs)
        
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Initialize or update request history for this IP
        if client_ip not in request_history:
            request_history[client_ip] = []
        
        # Clean old requests outside the window
        request_history[client_ip] = [
            timestamp for timestamp in request_history[client_ip]
            if timestamp > current_time - RATE_LIMIT_WINDOW
        ]
        
        # Check if this IP has made too many requests
        if len(request_history[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            print(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        # Add this request to the history
        request_history[client_ip].append(current_time)
        
        # Proceed with the original route function
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_security():
    """Global security checks before any request"""
    # Log request except for health checks
    if request.path != '/':
        print(f"{datetime.now().isoformat()} - {request.remote_addr} - {request.method} {request.path}")
    
    # Block if not in whitelist (when whitelist is enabled)
    if not check_ip_whitelist():
        print(f"Blocked unauthorized access from: {request.remote_addr}")
        abort(403)  # Forbidden
    
    # Block common attack paths
    blocked_paths = [
        '/.env', '/.git', '/wp-login.php', '/wp-admin', '/admin',
        '/boaform', '/portal', '/config', '/cgi-bin', '/xmlrpc.php'
    ]
    
    if any(request.path.startswith(path) for path in blocked_paths):
        print(f"Blocked suspicious request to {request.path} from {request.remote_addr}")
        abort(404)  # Not Found to avoid revealing information

# ... existing functions like get_video_info and sanitize_filename ...

@app.route("/record/", methods=["POST"])
@rate_limit
def record_audio():
    """클라이언트로부터 오디오 데이터를 받아 메모리에 저장합니다."""
    global audio_data
    
    try:
        if 'audio' not in request.files:
            return jsonify({"detail": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        # 파일 저장 대신 메모리에 바이트 데이터로 보관
        audio_bytes = audio_file.read()
        
        # 파일로 저장하지 않고 전역 변수에 보관
        audio_data = audio_bytes
        
        return jsonify({"message": "Audio data received successfully."})
        
    except Exception as e:
        print(f"Error in record_audio: {str(e)}")
        traceback.print_exc()
        return jsonify({"detail": f"Audio data processing failed: {str(e)}"}), 500

@app.route("/transcribe/", methods=["POST"])
@rate_limit
def transcribe_audio():            
    """메모리에 저장된 오디오 데이터를 Whisper로 인식합니다."""
    try:                                                                                                             
        global audio_data, model
        
        if not audio_data:
            return jsonify({"detail": "No audio data available"}), 400
        
        # Verify model is initialized
        if model is None:
            init_model()
            if model is None:  # Still None after initialization attempt
                return jsonify({"detail": "Speech recognition model unavailable"}), 500
            
        # 바이트 데이터를 임시 파일 객체로 변환
        audio_buffer = io.BytesIO(audio_data)
        
        try:
            # 임시 버퍼에서 Whisper로 직접 처리 - 언어 감지 먼저 수행
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
        except RuntimeError as rt_error:
            # Handle CUDA out of memory or other runtime errors
            if "CUDA" in str(rt_error) or "cuDNN" in str(rt_error):
                print(f"CUDA/cuDNN error: {str(rt_error)}")
                # Try to reinitialize with CPU
                try:
                    from faster_whisper import WhisperModel
                    model = WhisperModel("medium", device="cpu")
                    print("Reinitialized with CPU after CUDA error")
                    # Try again with CPU
                    audio_buffer.seek(0)
                    segments, info = model.transcribe(
                        audio_buffer,
                        beam_size=5,
                        word_timestamps=False,
                        language=None
                    )
                    result = " ".join([segment.text for segment in segments])
                    return jsonify({
                        "language": info.language, 
                        "text": result, 
                        "note": "Used CPU fallback due to CUDA error"
                    })
                except Exception as fallback_error:
                    print(f"CPU fallback also failed: {str(fallback_error)}")
                    return jsonify({
                        "detail": f"Transcription failed (CUDA error and CPU fallback failed): {str(fallback_error)}"
                    }), 500
            else:
                raise  # Re-raise if not CUDA related
                
    except Exception as e:
        print(f"General error in transcribe: {str(e)}")
        traceback.print_exc()
        return jsonify({"detail": f"Transcription failed: {str(e)}"}), 500

# ... existing routes for search_youtube, download_video, etc. ...

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for cloud provider's health monitoring."""
    gpu_info = "Not available"
    if torch.cuda.is_available():
        try:
            gpu_info = torch.cuda.get_device_name(0)
        except:
            gpu_info = "Error getting GPU info"
            
    return jsonify({
        "status": "healthy",
        "service": "stt_yt_api",
        "gpu_available": torch.cuda.is_available(),
        "gpu_info": gpu_info,
        "model_device": "cuda" if model and hasattr(model, "device") and "cuda" in model.device else "cpu",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    print(f"Server starting on port {PORT} in {ENV} mode")
    print(f"Security: Rate limiting {'enabled' if ENABLE_RATE_LIMITING else 'disabled'}")
    print(f"Security: IP whitelist {'enabled' if ALLOWED_IPS and ALLOWED_IPS != [''] else 'disabled'}")
    
    # Use the PORT environment variable provided by the cloud platform
    app.run(host="0.0.0.0", port=PORT)
EOF

# Create Dockerfile for the modified version
cat > Dockerfile.fixed << 'EOF'
FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables to help with cuDNN issues
ENV CT2_CUDA_MEMORY_INITIAL_SIZE=512
ENV CT2_CUDA_DYNAMIC_BUFFER=1
ENV CT2_CUDA_LOG_COMPILATION=0
ENV CT2_USE_INFERENCE_ENGINES=0

# Install requirements with pinned versions
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY server_modified.py server.py

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Export CUDA paths to help library discovery
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# Run the application
CMD ["python", "server.py"]
EOF

# Create requirements.txt file with specific ctranslate2 version
cat > requirements.txt << 'EOF'
flask==2.0.1
werkzeug==2.0.1
faster-whisper==0.9.0
ctranslate2==3.15.1
google-api-python-client==2.86.0
torch==2.0.1
yt-dlp==2023.7.6
numpy>=1.24.0
ffmpeg-python>=0.2.0
EOF

echo "==========================================="
echo "Files created successfully. To apply the fix:"
echo "1. Copy server_modified.py to your server"
echo "2. Build a new Docker image with the modified server"
echo ""
echo "Run the following commands on your VM:"
echo "==========================================="
echo "cd ~/stt_yt"
echo "sudo docker stop stt-yt-container-gpu"
echo "sudo docker rm stt-yt-container-gpu"
echo "sudo docker build -t stt-yt-gpu-fixed -f Dockerfile.fixed ."
echo "sudo docker run -d --gpus all -p 80:8000 \\"
echo "  -e PORT=8000 \\"
echo "  -e YOUTUBE_API_KEY=AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8 \\"
echo "  -e FLASK_ENV=production \\"
echo "  --restart always \\"
echo "  --name stt-yt-container-gpu-fixed stt-yt-gpu-fixed"
echo "==========================================="