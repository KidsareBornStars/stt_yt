from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.video import Video
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.core.video.video_ffpyplayer import VideoFFPy
from kivy.core.video import Video as CoreVideo
from kivy.core.text import LabelBase
import requests
import warnings
warnings.filterwarnings("ignore")
import sounddevice as sd
import scipy.io.wavfile as wavfile
import os
os.environ['PO_TOKEN'] = 'PO_TOKEN'
os.environ['VISITORDATA'] = 'VISITORDATA'
from pytubefix import YouTube

BASE_URL = "http://1.227.153.93:8000"

# 앱 시작 전에 FFPy 프로바이더 설정
CoreVideo._video = VideoFFPy

# 한글 폰트 등록
LabelBase.register(
    name='NanumGothic',
    fn_regular='fonts/NanumGothic.ttf'  # 나눔고딕 폰트 파일 경로
)

class MyApp(App):
    def build(self):
        Window.bind(on_keyboard=self.on_keyboard)
        
        self.layout = BoxLayout(orientation='vertical')
        
        # 상단에 정보를 표시할 Label 추가
        self.info_label = Label(
            text='음성 인식 대기중...',
            size_hint=(1, 0.1),  # 전체 너비의 10% 높이로 설정
            halign='center',
            font_name='NanumGothic'  # 등록한 폰트 이름 지정
        )
        self.layout.add_widget(self.info_label)
        
        # 기존 비디오 위젯
        self.video = Video(source='', state='stop', size_hint=(1, 0.9))
        self.layout.add_widget(self.video)
        return self.layout

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if key == 286:  # 녹음
            self.record_and_process(None)
            return True
        elif key == 287:  # 재생
            if hasattr(self, 'video'):
                self.video.state = 'play'
            return True
        elif key == 288:  # 일시정지
            if hasattr(self, 'video'):
                self.video.state = 'pause'
            return True
        elif key == 289:  # 정지
            if hasattr(self, 'video'):
                self.video.state = 'stop'
            return True
        return False

    def record_and_process(self, instance):
        self.record_audio()
        text = self.transcribe_audio()
        if text:
            video_id = self.search_youtube(text)
            if video_id:
                self.download_and_play(video_id)

    def record_audio(self):
        """Records audio on the client side and sends it to the server."""
        try:
            fs = 44100  # 샘플링 레이트
            duration = 7  # 녹음 시간 (초)
            
            self.info_label.text = "녹음 중..."
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()  # 녹음이 끝날 때까지 대기
            
            # WAV 파일로 저장
            output_file = "recorded_audio.wav"
            wavfile.write(output_file, fs, recording)
            
            # 서버로 파일 전송
            files = {'audio': open(output_file, 'rb')}
            response = requests.post(f"{BASE_URL}/record/", files=files)
            
            if response.status_code == 200:
                self.info_label.text = "녹음 완료"
                print(response.json()["message"])
            else:
                self.info_label.text = "녹음 전송 실패"
                print(f"Error: {response.json()['detail']}")
        except Exception as e:
            self.info_label.text = f"녹음 실패: {str(e)}"
            print(f"Recording error: {str(e)}")

    def transcribe_audio(self):
        """Calls the server to transcribe audio."""
        response = requests.post(f"{BASE_URL}/transcribe/")
        if response.status_code == 200:
            result = response.json()
            transcribed_text = result["text"]
            # Label 업데이트
            self.info_label.text = f'인식된 텍스트: {transcribed_text}'
            return transcribed_text
        else:
            self.info_label.text = '음성 인식 실패'
            print(f"Error: {response.json()['detail']}")

    def search_youtube(self, query):
        """Calls the server to search YouTube."""
        response = requests.post(f"{BASE_URL}/search_youtube/", json={"query": query})
        if response.status_code == 200:
            video_id = response.json()["video_id"]
            print(f"Found YouTube video ID: {video_id}")
            return video_id
        else:
            print(f"Error: {response.json()['detail']}")

    def download_and_play(self, video_id):
        """Downloads video from YouTube and returns the file path."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            yt = YouTube(video_url, use_po_token=True)
            ys = yt.streams.get_lowest_resolution()
            # 절대 경로로 저장
            video_path = os.path.abspath(ys.download(output_path=".", filename="video.mp4"))
            self.info_label.text += f'\n재생 중인 영상: {yt.title}'
            # 비디오 소스 설정 및 재생
            self.video.source = video_path
            self.video.state = 'play'
            return video_path, yt.title  # 경로와 제목 반환
        except Exception as e:
            self.info_label.text += '\n영상 다운로드 실패'
            raise Exception(f"Download failed: {str(e)}")  # 예외 처리

if __name__ == "__main__":
    MyApp().run()