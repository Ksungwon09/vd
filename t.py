import yt_dlp  
info=yt_dlp.YoutubeDL({'js_runtimes': {'node': {}}}).extract_info('https://www.youtube.com/watch?v=vS_MaVXRCek', download=False)  
