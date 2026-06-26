import yt_dlp
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'format': 'all',  # Maybe this helps?
}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=vS_MaVXRCek", download=False)
        print("Success! Title:", info.get('title'))
except Exception as e:
    print("Error:", str(e))
