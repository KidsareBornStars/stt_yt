from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.video import Video as UIVideo
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.video import Video  
from kivy.core.video.video_ffpyplayer import VideoFFPy
from kivy.core.text import LabelBase, DEFAULT_FONT
from kivy.utils import platform
import requests
import warnings
warnings.filterwarnings("ignore")
import sounddevice as sd
import scipy.io.wavfile as wavfile
import os
import io
import tempfile
from threading import Timer
import time
import traceback

# Get server URL from environment variable or use default
# Use the external IP address of your GCP VM
# You can change this SERVER_IP = os.environ.get('SERVER_IP', "34.22.84.227")  # Replace with your VM's IP 
# place with your VM's IP 
BASE_URL = f"http://34.22.84.227"

# For local testing
# BASE_URL = "http://localhost:8000"  # Local development

# To use the deployed server without modifying code, set the SERVER_IP environment variable:
# Windows: set SERVER_IP=your_vm_ip_address
# Linux/Mac: export SERVER_IP=your_vm_ip_address

# 기존 폰트 등록 코드 대체
def setup_system_fonts():
    """시스템 폰트를 사용하여 다국어 지원 설정"""
    if platform == 'win':
        # 윈도우의 경우 Malgun Gothic (맑은 고딕) 사용
        font_path = 'C:/Windows/Fonts/malgun.ttf'
        LabelBase.register(DEFAULT_FONT, font_path)
    elif platform == 'macosx':
        # macOS의 경우 Apple Gothic 또는 다른 시스템 폰트 사용
        font_path = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
        LabelBase.register(DEFAULT_FONT, font_path)
    elif platform == 'linux':
        # 리눅스의 경우 Noto Sans CJK 사용 (설치되어 있다면)
        try:
            import subprocess
            font_query = subprocess.check_output(['fc-match', '-f', '%{file}', 'Noto Sans CJK KR']).decode().strip()
            if font_query:
                LabelBase.register(DEFAULT_FONT, font_query)
        except:
            pass

# 앱 시작 시 호출
setup_system_fonts()

# Video 프로바이더 설정
Video._video = VideoFFPy


class MyApp(App):
    def __init__(self, **kwargs):
        super(MyApp, self).__init__(**kwargs)
        self.current_video_path = None
        self.downloaded_videos = []  # Keep track of downloaded videos
    
    def build(self):
        Window.bind(on_keyboard=self.on_keyboard)
        
        self.layout = BoxLayout(orientation='vertical')
        
        # 상단에 정보를 표시할 Label 추가
        self.info_label = Label(
            text='음성 인식 대기중...',
            size_hint=(1, 0.1),  # 전체 너비의 10% 높이로 설정
            halign='center',
            font_name=DEFAULT_FONT  # System font 사용
        )
        self.layout.add_widget(self.info_label)
        
        # 비디오 위젯 생성 시 ffpyplayer 옵션 설정
        self.video = UIVideo(source='', state='stop', size_hint=(1, 0.9), options={'eos': 'loop'})
        self.layout.add_widget(self.video)
        return self.layout

    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if key == 286:  # 녹음
            self.record_and_process(None)
            return True
        elif key in [287, 288, 289]:  # 재생, 일시정지, 정지
            return self.handle_video_control(key)
        return False

    def handle_video_control(self, key):
        """Handle video playback controls."""
        if not hasattr(self, 'video'):
            return False
            
        state_map = {
            287: 'play',    # 재생
            288: 'pause',   # 일시정지
            289: 'stop'     # 정지
        }
        
        if key in state_map:
            self.video.state = state_map[key]
            return True
        return False

    def record_and_process(self, instance):
        """Record audio, transcribe it, and play a related YouTube video."""
        try:
            self.info_label.text = "녹음 중..."
            if not self.record_audio():
                return
            
            self.info_label.text = "음성 인식 중..."
            text = self.transcribe_audio()
            
            if not text or text.strip() == "":
                self.info_label.text = "인식된 텍스트가 없습니다. 다시 시도해주세요."
                return
                
            self.info_label.text = f"인식된 텍스트: {text}\n비디오 검색 중..."
            video_id = self.search_youtube(text)
            
            if not video_id:
                self.info_label.text = f"'{text}'에 대한 비디오를 찾을 수 없습니다."
                return

            self.play_video(video_id)
            
        except requests.exceptions.ConnectionError:
            self.info_label.text = "서버 연결 실패. 네트워크 상태를 확인하세요."
        except Exception as e:
            self.info_label.text = f"오류 발생: {str(e)}"
            print(f"Error in record_and_process: {str(e)}")
            traceback.print_exc()

    def record_audio(self):
        """메모리 버퍼에 녹음한 후 서버로 직접 전송합니다."""
        try:
            fs = 44100  # 샘플링 레이트
            duration = 7  # 녹음 시간 (초)
            
            self.info_label.text = "녹음 중..."
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()  # 녹음이 끝날 때까지 대기
            
            # WAV 파일로 저장하는 대신 BytesIO 객체에 저장
            audio_buffer = io.BytesIO()
            # 헤더 정보(샘플레이트, 채널 등) 포함하여 WAV 형식으로 버퍼에 저장
            wavfile.write(audio_buffer, fs, recording)
            audio_buffer.seek(0)  # 버퍼 포인터를 처음으로 이동
            
            # 서버로 버퍼 직접 전송
            files = {'audio': ('audio.wav', audio_buffer, 'audio/wav')}
            response = requests.post(f"{BASE_URL}/record/", files=files)
            
            if response.status_code == 200:
                self.info_label.text = "녹음 완료"
                print(response.json()["message"])
                return True
            else:
                error_msg = response.json().get('detail', '알 수 없는 오류')
                self.info_label.text = f"녹음 전송 실패: {error_msg}"
                print(f"Error: {error_msg}")
                return False
            
        except Exception as e:
            self.info_label.text = f"녹음 실패: {str(e)}"
            print(f"Recording error: {str(e)}")
            return False

    def transcribe_audio(self):
        """Calls the server to transcribe audio."""
        response = requests.post(f"{BASE_URL}/transcribe/")
        if response.status_code == 200:
            result = response.json()
            transcribed_text = result["text"]
            return transcribed_text
        else:
            error_msg = response.json().get('detail', '알 수 없는 오류')
            self.info_label.text = f'음성 인식 실패: {error_msg}'
            print(f"Error: {error_msg}")
            return None

    def search_youtube(self, query):
        """Calls the server to search YouTube."""
        response = requests.post(f"{BASE_URL}/search_youtube/", json={"query": query})
        if response.status_code == 200:
            video_id = response.json()["video_id"]
            print(f"Found YouTube video ID: {video_id}")
            return video_id
        else:
            error_msg = response.json().get('detail', '알 수 없는 오류')
            self.info_label.text = f"검색 실패: {error_msg}"
            print(f"Error: {error_msg}")
            return None

    def play_video(self, video_id):
        """서버에서 비디오를 다운로드한 후 재생합니다."""
        try:
            self.info_label.text = "비디오 다운로드 중..."
            
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"temp_video_{video_id}.mp4")
            
            # 서버로부터 직접 비디오 다운로드
            with requests.post(
                f"{BASE_URL}/download_video/", 
                json={"video_id": video_id}, 
                stream=True
            ) as response:
                if response.status_code != 200:
                    error_msg = response.json().get('detail', '알 수 없는 오류')
                    self.info_label.text = f'비디오 다운로드 실패: {error_msg}'
                    return None
                    
                # 응답 헤더에서 비디오 제목 가져오기
                video_title = response.headers.get('X-Video-Title', 'Unknown Video')
                    
                total_size = int(response.headers.get('content-length', 0))
                
                with open(temp_path, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                            downloaded += len(chunk)
                            f.write(chunk)
                            progress = int(downloaded / total_size * 100)
                            self.info_label.text = f"다운로드 중... {progress}%"
            
            # 다운로드 성공한 경우 목록에 추가
            self.downloaded_videos.append(temp_path)
            self.current_video_path = temp_path
            self.cleanup_old_videos()
            
            # 비디오 위젯 업데이트 및 재생
            self.update_video_widget(temp_path, video_title)
            return video_title
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"비디오 처리 실패: {error_type} - {error_msg}")
            traceback.print_exc()
            self.info_label.text = f'비디오 처리 실패: {error_type} - {error_msg}'
            return None
            
    def download_video(self, video_id, video_url):
        """비디오 다운로드 로직."""
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_video_{video_id}.mp4")
        
        self.info_label.text = "비디오 다운로드 중..."
        response = requests.get(video_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        try:
            with open(temp_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    chunk_size = 1024 * 1024  # 1MB 단위로 다운로드
                    for data in response.iter_content(chunk_size=chunk_size):
                        downloaded += len(data)
                        f.write(data)
                        progress = int((downloaded / total_size) * 100)
                        self.info_label.text = f"다운로드 중... {progress}%"
                        
            # 다운로드 성공한 경우에만 목록에 추가
            self.downloaded_videos.append(temp_path)
            self.current_video_path = temp_path
            self.cleanup_old_videos()
            return temp_path
        except Exception as e:
            self.info_label.text = f"다운로드 실패: {str(e)}"
            return None
        
    def update_video_widget(self, video_path, video_title):
        """비디오 위젯 업데이트 및 재생."""
        try:
            # 이전 비디오 정리
            if hasattr(self, 'video') and self.video:
                self.video.state = 'stop'
                self.layout.remove_widget(self.video)
            
            # Make sure the path exists
            if not os.path.exists(video_path):
                self.info_label.text = f"비디오 파일을 찾을 수 없음: {video_path}"
                return
                
            print(f"Playing video from: {video_path}")
            
            # 새 비디오 위젯 생성
            self.video = UIVideo(
                source=video_path,
                state='stop',
                size_hint=(1, 0.9),
                options={'eos': 'loop'}
            )
            
            self.layout.add_widget(self.video)
            
            # Wait a moment before playing
            Clock.schedule_once(lambda dt: setattr(self.video, 'state', 'play'), 0.5)
            self.info_label.text = f'재생 중인 영상: {video_title}'
        except Exception as e:
            self.info_label.text = f"비디오 재생 실패: {str(e)}"
            print(f"Error in update_video_widget: {traceback.format_exc()}")
    def cleanup_old_videos(self):
        """이전에 다운로드한 임시 비디오 파일을 삭제합니다."""
        # First, stop the current video playback
        if hasattr(self, 'video') and self.video:
            self.video.state = 'stop'
        
        for video_path in self.downloaded_videos[:]:
            try:
                # Only delete if it's not the currently playing video
                if video_path != self.current_video_path:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                        print(f"임시 파일 삭제: {video_path}")
                    self.downloaded_videos.remove(video_path)
            except Exception as e:
                print(f"파일 삭제 실패: {str(e)}: {video_path}")

    def schedule_cleanup(self, path, delay=5):
        """파일 삭제를 지연시켜 파일 잠금 문제를 방지합니다."""
        def delayed_delete():
            try:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"지연 삭제 성공: {path}")
                    if path in self.downloaded_videos:
                        self.downloaded_videos.remove(path)
            except Exception as e:
                print(f"지연 삭제 실패: {str(e)}: {path}")
        
        # Schedule deletion after specified delay (seconds)
        Timer(delay, delayed_delete).start()

    def on_stop(self):
        """앱 종료 시 임시 파일 정리"""
        # Stop video playback
        if hasattr(self, 'video') and self.video:
            self.video.state = 'stop'
            
        # Small delay to ensure video player releases the file
        time.sleep(0.5)
        
        # Try to delete all temporary files
        for video_path in self.downloaded_videos[:]:
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"앱 종료 시 파일 삭제: {video_path}")
                    self.downloaded_videos.remove(video_path)
            except Exception as e:
                print(f"종료 시 파일 삭제 실패: {str(e)}: {video_path}")
                
        return super(MyApp, self).on_stop()

if __name__ == "__main__":
    # 디버깅용 로그 출력 활성화
    # import logging
    # logger = logging.getLogger('kivy')
    # logger.setLevel(logging.DEBUG)
    
    MyApp().run()