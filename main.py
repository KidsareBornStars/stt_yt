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
warnings.filterwarnings("ignore")

class MyApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical')
        self.button = Button(text="Start Recording", size_hint=(1, 0.2))
        self.button.bind(on_press=self.record_and_transcribe)
        self.video = Video(size_hint=(1, 0.8))

        self.layout.add_widget(self.video)
        self.layout.add_widget(self.button)
        return self.layout

    def record_and_transcribe(self, instance):
        # Record audio and save it as 'audio.wav'
        os.system('ffmpeg -f dshow -i audio="마이크(2- JBL Quantum350 Wireless)" -t 5 -y audio.wav')

        
        # Transcribe using Whisper
        model = whisper.load_model("turbo")

        # load audio and pad/trim it to fit 30 seconds
        audio = whisper.load_audio("audio.wav")
        audio = whisper.pad_or_trim(audio)

        # make log-Mel spectrogram and move to the same device as the model
        mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)

        # detect the spoken language
        _, probs = model.detect_language(mel)
        print(f"Detected language: {max(probs, key=probs.get)}")

        # decode the audio
        options = whisper.DecodingOptions()
        result = whisper.decode(model, mel, options)

        # print the recognized text
        print(result.text)

        # Search on YouTube
        video_id = self.search_youtube(result.text)
        self.play_video(video_id)

    def search_youtube(self, query):
        api_key = 'MY_API_KEY'
        youtube = build("youtube", "v3", developerKey=api_key)
        request = youtube.search().list(q=query, part="snippet", type="video", maxResults=1)
        response = request.execute()
        return response["items"][0]["id"]["videoId"]

    def play_video(self, video_id):
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(video_url, on_progress_callback=on_progress)
        print(yt.title)

        ys = yt.streams.get_audio_only()
        ys.download('.','audio.wav')

        # Play using the default media player
        if os.name == "nt":  # Windows
            os.system("start audio.wav")
        elif os.name == "posix":  # macOS or Linux
            os.system("open sample.mp3" if "darwin" in os.uname().sysname.lower() else "xdg-open sample.mp3")
if __name__ == "__main__":
    MyApp().run()
