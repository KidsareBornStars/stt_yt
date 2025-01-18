from pytubefix import YouTube
video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
yt = YouTube(video_url, use_po_token=True)
ys = yt.streams.get_lowest_resolution()

print(yt.title)