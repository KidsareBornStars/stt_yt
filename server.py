from flask import Flask, request, jsonify, send_file
from faster_whisper import WhisperModel
from googleapiclient.discovery import build
import torch
import os
os.environ['YOUTUBE_API_KEY'] = 'AIzaSyBvIAUcY-LNvtWSxl2smOLhni_5NhetKE8'
os.environ['FLASK_ENV'] = 'development'
import warnings
warnings.filterwarnings("ignore")
import io
import yt_dlp

app = Flask(__name__)

# Global Whisper model initialization
model = WhisperModel("turbo", device="cuda" if torch.cuda.is_available() else "cpu")

# 서버 시작 전에 전역 변수 초기화
audio_data = None

@app.route("/record/", methods=["POST"])
def record_audio():
    """클라이언트로부터 오디오 데이터를 받아 메모리에 저장합니다."""
    try:
        if 'audio' not in request.files:
            return jsonify({"detail": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        # 파일 저장 대신 메모리에 바이트 데이터로 보관
        audio_bytes = audio_file.read()
        
        # 파일로 저장하지 않고 전역 변수에 보관
        global audio_data
        audio_data = audio_bytes
        
        return jsonify({"message": "Audio data received successfully."})
    except Exception as e:
        return jsonify({"detail": f"Audio data processing failed: {str(e)}"}), 500

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
def search_youtube():
    """Searches YouTube for the given query and returns the video ID."""
    api_key = os.getenv('YOUTUBE_API_KEY')  
    youtube = build("youtube", "v3", developerKey=api_key)
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
def download_video():
    """Download a YouTube video and stream it to the client."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        # Generate unique filename
        import time
        temp_filepath = os.path.join(temp_dir, f"temp_video_{video_id}_{int(time.time())}.mp4")
        
        # Download options
        ydl_opts = {
            'format': 'mp4[height<=480]/bestvideo[height<=480]+bestaudio/best[height<=480]',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'outtmpl': temp_filepath,
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'Unknown')
        
        response = send_file(
            temp_filepath,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f"{video_title}.mp4"
        )
        response.headers['X-Video-Title'] = video_title
        # Stream the file to the client
        return response
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Video download failed: {error_type} - {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"detail": f"Video download failed: {error_type} - {error_msg}"}), 500

@app.route("/check_video_size/", methods=["POST"])
def check_video_size():
    """Check YouTube video size and duration."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            'format': 'best[height<=480]',  # 포맷 조건 단순화
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'skip_download': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # 비디오 정보 추출
            filesize = info.get('filesize') or info.get('filesize_approx')
            duration = info.get('duration')
            title = info.get('title', 'Unknown')
            
            # 시간 기준도 추가 (10분 초과는 일반적으로 단일 곡이 아님)
            time_limit_seconds = 10 * 60

            too_long = False

            if duration and duration > time_limit_seconds:
                too_long = True
                print(f"비디오 길이 제한 초과: {duration/60:.2f}분 > 10분")
            
            # 결과 반환
            result = {
                'title': title,
                'filesize': filesize,
                'filesize_mb': filesize/1024/1024 if filesize else None,
                'duration': duration,
                'duration_min': duration/60 if duration else None,
                'too_long': too_long,
                'is_single_song': not too_long
            }
            
            return jsonify(result)
                
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"비디오 크기 확인 실패: {error_type} - {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"detail": f"Video size check failed: {error_type} - {error_msg}"}), 500


@app.route("/download_merged_video/", methods=["POST"])
def download_merged_video():
    """비디오와 오디오를 병합하여 다운로드합니다."""
    try:
        data = request.get_json()
        video_id = data["video_id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 임시 파일을 저장할 디렉토리 생성
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'merge_output_format': 'mp4'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'Unknown')
            output_path = os.path.join(temp_dir, f"{info['id']}.mp4")
            
            response = send_file(
                output_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=f"{video_title}.mp4"
            )
            response.headers['X-Video-Title'] = video_title
            return response
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"병합된 비디오 다운로드 실패: {error_type} - {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"detail": f"Failed to download merged video: {error_type} - {error_msg}"}), 500

if __name__ == "__main__":
    app.run(host="192.168.55.18", port=8000)
