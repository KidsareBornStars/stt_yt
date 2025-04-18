from flask import Flask, request, jsonify, send_file, abort
from faster_whisper import WhisperModel
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

# Environment variables - use environment variables from cloud service
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

app = Flask(__name__)

# Request rate limiting
request_history = {}  # IP -> list of timestamps

# Global Whisper model initialization
print("Initializing Whisper model...")
try:
    # First try with CUDA
    use_gpu = torch.cuda.is_available()
    model = WhisperModel("medium", device="cuda" if use_gpu else "cpu")
    print(f"Using device: {'cuda' if use_gpu else 'cpu'}")
    if use_gpu:
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"Error initializing with CUDA: {str(e)}")
    print("Falling back to CPU mode...")
    model = WhisperModel("medium", device="cpu")
    print("Using device: cpu (fallback)")

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

    # Block common non-HTTP requests
    if request.method == 'GET' and 'HTTP/2.0' in str(request.environ):
        abort(505)  # HTTP Version Not Supported
        
    # Check content type for API endpoints
    if request.path == '/record/' and request.method == 'POST':
        if 'multipart/form-data' not in request.content_type:
            abort(415)  # Unsupported Media Type

def get_video_info(video_id, download=False, format_options=None):
    """Get video information using yt_dlp with specified options."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    if format_options is None:
        format_options = 'best[height<=720]'
        
    ydl_opts = {
        'format': format_options,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'skip_download': not download
    }
    
    # Add output template if downloading
    if download:
        ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(video_url, download=download)
    except Exception as e:
        print(f"Video info extraction failed: {type(e).__name__} - {str(e)}")
        traceback.print_exc()
        raise e

def sanitize_filename(title, video_id):
    """파일 이름에 사용할 수 없는 문자를 제거합니다."""
    safe_title = re.sub(r'[^\x00-\x7F]+', '', title)  # ASCII 문자만 유지
    safe_title = re.sub(r'[<>:"/\\|?*]', '', safe_title)  # Windows 파일명 제한 문자 제거
    safe_title = safe_title.strip()  # 앞뒤 공백 제거
    
    if not safe_title:  # 제목이 모두 제거된 경우
        safe_title = f"video_{video_id}"
        
    return safe_title

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
        global audio_data
        if not audio_data:
            return jsonify({"detail": "No audio data available"}), 400
            
        # 바이트 데이터를 임시 파일 객체로 변환
        audio_buffer = io.BytesIO(audio_data)
        
        # 임시 버퍼에서 Whisper로 직접 처리
        # 언어 감지 먼저 수행
        segments, info = model.transcribe(
            audio_buffer,
            beam_size=5,
            word_timestamps=False,
            language=None  # 자동 언어 감지 활성화
        )
        
        detected_language = info.language
        print(f"감지된 언어: {detected_language}")
        print(f"감지된 텍스트: {' '.join([segment.text for segment in segments])}")
        
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
    except Exception as e:
        return jsonify({"detail": f"Transcription failed: {str(e)}"}), 500

@app.route("/search_youtube/", methods=["POST"])
@rate_limit
def search_youtube():
    """Searches YouTube for the given query and returns the video ID."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    try:
        data = request.get_json()
        response = youtube.search().list(
            q=data["query"], part="snippet", type="video", maxResults=1
        ).execute()
        video_id = response["items"][0]["id"]["videoId"]
        return jsonify({"video_id": video_id})
    except Exception as e:
        return jsonify({"detail": f"YouTube search failed: {str(e)}"}), 500

@app.route("/download_video/", methods=["POST"])
@rate_limit
def download_video():
    """Download a YouTube video and stream it to the client."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        
        format_options = 'mp4[height<=480]/bestvideo[height<=480]+bestaudio/best[height<=480]'
        info = get_video_info(video_id, download=True, format_options=format_options)
        
        video_title = info.get('title', 'Unknown')
        safe_title = sanitize_filename(video_title, video_id)
        
        output_path = os.path.join(TEMP_DIR, f"{info['id']}.mp4")
        
        response = send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f"{safe_title}.mp4"
        )
        response.headers['X-Video-Title'] = safe_title
        return response
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Video download failed: {error_type} - {error_msg}")
        traceback.print_exc()
        return jsonify({"detail": f"Video download failed: {error_type} - {error_msg}"}), 500

@app.route("/check_video_size/", methods=["POST"])
@rate_limit
def check_video_size():
    """YouTube 비디오 정보를 확인하고 반환합니다."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        
        info = get_video_info(video_id)
        
        return jsonify({
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration'),
            'filesize': info.get('filesize'),
            'url': info.get('url'),
            'format': info.get('format'),
            'height': info.get('height'),
            'width': info.get('width')
        })
                
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"비디오 정보 확인 실패: {error_type} - {error_msg}")
        return jsonify({"detail": f"Video info check failed: {error_type} - {error_msg}"}), 500

@app.route("/get_stream_url/", methods=["POST"])
@rate_limit
def get_stream_url():
    """YouTube 비디오의 스트림 URL을 반환합니다."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        
        info = get_video_info(video_id)
        
        return jsonify({
            'stream_url': info['url'],
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration'),
            'format': info.get('format')
        })
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"스트림 URL 추출 실패: {error_type} - {error_msg}")
        return jsonify({"detail": f"Failed to get stream URL: {error_type} - {error_msg}"}), 500

@app.route("/download_merged_video/", methods=["POST"])
@rate_limit
def download_merged_video():
    """중간 품질의 비디오와 오디오를 병합하여 다운로드합니다."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        
        format_options = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
        info = get_video_info(video_id, download=True, format_options=format_options)
        
        video_title = info.get('title', 'Unknown')
        
        # 파일 이름에서 사용할 수 없는 문자 제거
        safe_title = sanitize_filename(video_title, video_id)
        
        output_path = os.path.join(TEMP_DIR, f"{info['id']}.mp4")
        
        response = send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f"{safe_title}.mp4"
        )
        
        response.headers['X-Video-Title'] = safe_title
        return response
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"병합된 비디오 다운로드 실패: {error_type} - {error_msg}")
        traceback.print_exc()
        return jsonify({"detail": f"Failed to download merged video: {error_type} - {error_msg}"}), 500

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for cloud provider's health monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "stt_yt_api",
        "gpu_available": torch.cuda.is_available(),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    print(f"Server starting on port {PORT} in {ENV} mode")
    print(f"Security: Rate limiting {'enabled' if ENABLE_RATE_LIMITING else 'disabled'}")
    print(f"Security: IP whitelist {'enabled' if ALLOWED_IPS and ALLOWED_IPS != [''] else 'disabled'}")
    
    # Use the PORT environment variable provided by the cloud platform
    app.run(host="0.0.0.0", port=PORT)