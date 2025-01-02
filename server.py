from fastapi import FastAPI, UploadFile, HTTPException
from pydantic import BaseModel
import whisper
from pytubefix import YouTube
from googleapiclient.discovery import build
import os
import subprocess
import shutil
import sounddevice as sd
import warnings
warnings.filterwarnings("ignore")

app = FastAPI()

# Global Whisper model initialization
model = whisper.load_model("turbo")

class YouTubeSearchRequest(BaseModel):
    query: str

@app.post("/record/")
async def record_audio():
    """Records audio from the specified microphone and saves it as 'audio.wav'."""
    output_file = "audio.wav"
    try:
        devices = sd.query_devices()
        input_index = sd.default.device[0]
        input_device = devices[input_index]["name"]

        # FFmpeg command to record audio
        command = f'ffmpeg -f dshow -i audio="{input_device}" -t 5 -y audio.wav'
        subprocess.run(command, shell=True, check=True)
        return {"message": "Audio recorded successfully.", "file": output_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio recording failed: {str(e)}")

@app.post("/transcribe/")
async def transcribe_audio():
    """Transcribes 'audio.wav' using Whisper and returns the recognized text."""
    try:
        # Load and process the audio file
        audio = whisper.load_audio("audio.wav")
        audio = whisper.pad_or_trim(audio)

        # Create Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)

        # Detect language
        _, probs = model.detect_language(mel)
        language = max(probs, key=probs.get)
        
        # Decode audio
        options = whisper.DecodingOptions()
        result = whisper.decode(model, mel, options)

        return {"language": language, "text": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.post("/search_youtube/")
async def search_youtube(request: YouTubeSearchRequest):
    """Searches YouTube for the given query and returns the video ID."""
    api_key = 'MY_API_KEY'  # Replace with your actual API key
    youtube = build("youtube", "v3", developerKey=api_key)
    try:
        response = youtube.search().list(
            q=request.query, part="snippet", type="video", maxResults=1
        ).execute()
        video_id = response["items"][0]["id"]["videoId"]
        return {"video_id": video_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube search failed: {str(e)}")

@app.get("/download_and_play/{video_id}")
async def download_and_play(video_id: str):
    """Downloads audio from a YouTube video and plays it."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        yt = YouTube(video_url)
        ys = yt.streams.get_audio_only()
        ys.download(output_path=".", filename="audio.mp3")

        # Play audio file
        if os.name == "nt":  # Windows
            os.system("start audio.mp3")
        elif os.name == "posix":  # macOS or Linux
            os.system("open audio.mp3" if "darwin" in os.uname().sysname.lower() else "xdg-open audio.mp3")
        return {"message": "Audio downloaded and played successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Playback failed: {str(e)}")
