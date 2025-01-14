from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.video import Video
import whisper
from pytubefix import YouTube
from pytubefix.cli import on_progress
from googleapiclient.discovery import build
import os
import sounddevice as sd
import warnings
import torch
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
        # Record audio and save it as 'audio.wav'
        os.system('ffmpeg -f avfoundation -i ":0" -t 5 -y audio.wav')

        # # load audio and pad/trim it to fit 30 seconds
        # audio = whisper.load_audio("audio.wav")
        # audio = whisper.pad_or_trim(audio)

        # # make log-Mel spectrogram and move to the same device as the model
        # mel = whisper.log_mel_spectrogram(audio, n_mels=self.model.dims.n_mels).to(self.model.device)

        # # detect the spoken language
        # _, probs = self.model.detect_language(mel)
        # print(f"Detected language: {max(probs, key=probs.get)}")

        
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
            beam_size=2,
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
