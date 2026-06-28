import yt_dlp

ydl_opts = {
    "extractor_args": {"youtube": {"player_client": ["android", "web", "ios"]}},
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
