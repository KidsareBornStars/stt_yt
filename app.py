import requests
import warnings
warnings.filterwarnings("ignore")
BASE_URL = "http://192.168.55.18:8000"

def record_audio():
    """Calls the server to record audio."""
    response = requests.post(f"{BASE_URL}/record/")
    if response.status_code == 200:
        print(response.json()["message"])
    else:
        print(f"Error: {response.json()['detail']}")

def transcribe_audio():
    """Calls the server to transcribe audio."""
    response = requests.post(f"{BASE_URL}/transcribe/")
    if response.status_code == 200:
        result = response.json()
        print(f"Detected language: {result['language']}")
        print(f"Transcribed text: {result['text']}")
        return result["text"]
    else:
        print(f"Error: {response.json()['detail']}")

def search_youtube(query):
    """Calls the server to search YouTube."""
    response = requests.post(f"{BASE_URL}/search_youtube/", json={"query": query})
    if response.status_code == 200:
        video_id = response.json()["video_id"]
        print(f"Found YouTube video ID: {video_id}")
        return video_id
    else:
        print(f"Error: {response.json()['detail']}")

def download_and_play(video_id):
    """Calls the server to download and play YouTube audio."""
    response = requests.get(f"{BASE_URL}/download_and_play/{video_id}")
    if response.status_code == 200:
        print(response.json()["message"])
    else:
        print(f"Error: {response.json()['detail']}")

if __name__ == "__main__":
    print("Starting client...")
    record_audio()
    text = transcribe_audio()
    if text:
        video_id = search_youtube(text)
        if video_id:
            download_and_play(video_id)