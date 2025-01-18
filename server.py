from flask import Flask, request, jsonify
from faster_whisper import WhisperModel
from pytubefix import YouTube
from pytubefix.cli import on_progress
from googleapiclient.discovery import build
import torch
import os
os.environ['YOUTUBE_API_KEY'] = 'MY_YOUTUBE_API_KEY'
import warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)

# Global Whisper model initialization
model = WhisperModel("turbo", device="cuda" if torch.cuda.is_available() else "cpu")

@app.route("/record/", methods=["POST"])
def record_audio():
    """Receives audio file from client and saves it as 'audio.wav'."""
    try:
        if 'audio' not in request.files:
            return jsonify({"detail": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        audio_file.save('audio.wav')
        
        return jsonify({"message": "Audio file received successfully.", "file": 'audio.wav'})
    except Exception as e:
        return jsonify({"detail": f"Audio file processing failed: {str(e)}"}), 500

@app.route("/transcribe/", methods=["POST"])
def transcribe_audio():
    """Transcribes 'audio.wav' using Whisper and returns the recognized text."""
    try:
        # 언어 감지 먼저 수행
        segments, info = model.transcribe(
            "audio.wav",
            beam_size=5,
            word_timestamps=False,
            language=None  # 자동 언어 감지 활성화
        )
        
        detected_language = info.language
        print(f"감지된 언어: {detected_language}")
        
        # 감지된 언어로 다시 전사
        segments, _ = model.transcribe(
            "audio.wav",
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

@app.route("/download_and_play/<video_id>", methods=["GET"])
def download_and_play(video_id):
    """Downloads video from YouTube and returns the file path."""
    return jsonify({"detail": "This endpoint is no longer available."}), 410

if __name__ == "__main__":
    app.run(host="192.168.55.18", port=8000)
