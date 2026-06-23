import yt_dlp  
info=yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True, 'format': 'all', 'ignoreerrors': False}).extract_info('https://www.youtube.com/watch?v=vS_MaVXRCek', download=False)  
