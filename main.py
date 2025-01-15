from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.video import Video
from pytubefix import YouTube
from pytubefix.cli import on_progress
from googleapiclient.discovery import build
import os
# os.environ['YOUTUBE_API_KEY'] = 'your_api_key_here'
import sounddevice as sd
import warnings
import torch
import scipy.io.wavfile as wavfile
from faster_whisper import WhisperModel
warnings.filterwarnings("ignore")

class MyApp(App):
    def build(self):
        api_key = os.getenv('YOUTUBE_API_KEY')
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.model = WhisperModel("turbo", device="cuda" if torch.cuda.is_available() else "cpu")
        self.layout = BoxLayout(orientation='vertical')
        self.button = Button(text="Start Recording", size_hint=(1, 0.2))
        self.button.bind(on_press=self.record_and_transcribe)
        self.video = Video(size_hint=(1, 0.8))


        self.layout.add_widget(self.video)
        self.layout.add_widget(self.button)
        return self.layout

    def record_and_transcribe(self, instance):
        # OS 독립적인 오디오 녹음 구현
        fs = 44100  # 샘플링 레이트
        duration = 7  # 녹음 시간 (초)
        
        print("녹음을 시작합니다...")
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()  # 녹음이 끝날 때까지 대기
        
        # WAV 파일로 저장
        wavfile.write('audio.wav', fs, recording)
        
        # 언어 감지 먼저 수행
        segments, info = self.model.transcribe(
            "audio.wav",
            beam_size=2,
            word_timestamps=False,
            language=None  # 자동 언어 감지 활성화
        )
        
        detected_language = info.language
        print(f"감지된 언어: {detected_language}")
        
        # 감지된 언어로 다시 전사
        segments, _ = self.model.transcribe(
            "audio.wav",
            beam_size=5,
            word_timestamps=False,
            language=detected_language  # 감지된 언어 사용
        )
        result = " ".join([segment.text for segment in segments])

        # print the recognized text
        print(result)

        # Search on YouTube
        video_id = self.search_youtube(result)
        self.play_video(video_id)

    def search_youtube(self, query):
        request = self.youtube.search().list(
            q=query,
            part="id",
            type="video",
            maxResults=1,
            fields="items(id/videoId)"
        )
        response = request.execute()    
        return response["items"][0]["id"]["videoId"]

    def play_video(self, video_id):
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(video_url, on_progress_callback=on_progress)
        print(yt.title)

        # 오디오 스트림 품질 낮추기
        ys = yt.streams.filter(only_audio=True, abr='128kbps').first()
        ys.download('.','audio.wav')

        # Play using the default media player
        if os.name == "nt":  # Windows
            os.system("start audio.wav")
        elif os.name == "posix":  # macOS or Linux
            if "darwin" in os.uname().sysname.lower():  # macOS
                os.system("afplay audio.wav")
            else:  # Linux
                os.system("xdg-open audio.wav")
if __name__ == "__main__":
    MyApp().run()
