import yt_dlp
import os
import tempfile
import sys

# Import app logic to decrypt cookie
sys.path.append("/code")
from app.security import decrypt_cookie

enc_file = "/code/data/cookies/sutingstar19@gmail.com.enc"

if not os.path.exists(enc_file):
    print("No cookie found")
    sys.exit(1)

with open(enc_file, "rb") as f:
    dec = decrypt_cookie(f.read())

fd, temp_path = tempfile.mkstemp(suffix=".txt")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(dec)

ydl_opts = {
    "cookiefile": temp_path,
    "extractor_args": {
        "youtube": {"player_client": ["android", "web", "ios"]},
        "youtubepot-bgutilhttp": {"base_url": ["http://pot-provider:4416"]}
    },
    "remote_components": ["ejs:github"]
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    try:
        info = ydl.extract_info("https://www.youtube.com/watch?v=wQg6ecwrPAE", download=False)
        formats = info.get("formats", [])
        print("Total formats:", len(formats))
        for f in formats:
            if "storyboard" not in f.get("format_note", ""):
                print(f.get("format_id"), f.get("vcodec"), f.get("acodec"), f.get("resolution"), f.get("format_note"))
    except Exception as e:
        print("Error:", e)
