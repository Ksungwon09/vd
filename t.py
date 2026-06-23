import yt_dlp  
info=yt_dlp.YoutubeDL({'quiet': False, 'skip_download': True, 'format': 'all', 'ignoreerrors': False, 'cookiefile': 'data/cookies/admin.txt', 'remote_components': ['ejs:github']}).extract_info('https://www.youtube.com/watch?v=1Dd_oX-KSNM', download=False)  
print(len(info.get('formats', [])))  
