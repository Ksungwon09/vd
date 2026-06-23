import sys
import yt_dlp

ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'ignoreerrors': True,
    'format': 'all',
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=vS_MaVXRCek", download=False)
        raw_formats = info.get('formats', [])
        print("Num raw formats:", len(raw_formats))
        for f in raw_formats:
            print(f.get('format_id'), "v:", f.get('vcodec'), "a:", f.get('acodec'), "h:", f.get('height'))
except Exception as e:
    print("Error:", str(e))
