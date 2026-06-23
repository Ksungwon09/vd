import asyncio
import os
import uuid
import sys
import subprocess
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
import re
import yt_dlp
from app import models
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from app.security import get_current_active_user, create_download_token, get_current_user_from_token_query

router = APIRouter(prefix="/video", tags=["video"])

# Generic modern browser User-Agent to avoid basic IP bans
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIES_DIR = "data/cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

@router.get("/info")
@limiter.limit("10/minute")
async def get_video_info(
    request: Request,
    url: str = Query(..., description="The URL of the video"),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Extracts metadata for the given video URL, including title, thumbnail, and available formats.
    Requires an authenticated and approved user.
    """
    def extract_info():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ignoreerrors': True,
            'format': 'all',  # Prevent default format selection from failing
            'http_headers': {
                'User-Agent': USER_AGENT
            }
        }
        cookie_file = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.to_thread(extract_info)
        if not info:
            raise Exception("Video information could not be extracted.")
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg or "cookies" in error_msg.lower():
            raise HTTPException(status_code=403, detail="COOKIE_ERROR")
        if "Requested format is not available" in error_msg:
            raise HTTPException(status_code=403, detail="COOKIE_ERROR")
        raise HTTPException(status_code=400, detail=f"Failed to extract info: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract info: {str(e)}")

    title = info.get('title', 'Unknown Title')
    thumbnail = info.get('thumbnail', '')
    raw_formats = info.get('formats', [])

    video_formats = {}
    audio_formats = []

    for f in raw_formats:
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        height = f.get('height')

        # Audio only
        if vcodec == 'none' and acodec != 'none':
            audio_formats.append(f)
            continue

        # Video
        if vcodec != 'none' and height:
            def get_compatibility_score(fmt):
                score = 0
                ext = fmt.get('ext', '')
                vc = fmt.get('vcodec', '')
                if ext == 'mp4':
                    score += 100
                # H.264 (avc1) is highly compatible with all players
                if vc.startswith('avc1'):
                    score += 50
                # VP9 is better than AV1 for some players
                elif vc.startswith('vp09'):
                    score += 20
                return score

            if height not in video_formats:
                video_formats[height] = f
            else:
                current_f = video_formats[height]
                if get_compatibility_score(f) > get_compatibility_score(current_f):
                    video_formats[height] = f
                elif get_compatibility_score(f) == get_compatibility_score(current_f):
                    video_formats[height] = f

    formats = []
    
    # Sort heights descending
    for h in sorted(video_formats.keys(), reverse=True):
        vf = video_formats[h]
        if h >= 2160:
            label = f"4K 초고화질 ({h}p)"
        elif h >= 1440:
            label = f"2K 고화질 ({h}p)"
        elif h >= 1080:
            label = f"FHD 표준화질 ({h}p)"
        elif h >= 720:
            label = f"HD 일반화질 ({h}p)"
        else:
            label = f"SD 저화질 ({h}p)"

        formats.append({
            "format_id": vf.get("format_id"),
            "resolution": label,
            "ext": "mp4",
            "filesize": vf.get("filesize") or vf.get("filesize_approx"),
            "description": "영상과 소리가 포함된 파일입니다."
        })

    if audio_formats:
        best_audio = audio_formats[-1]
        formats.append({
            "format_id": best_audio.get("format_id"),
            "resolution": "음원 전용 (최고 음질)",
            "ext": best_audio.get("ext", "m4a"),
            "filesize": best_audio.get("filesize") or best_audio.get("filesize_approx"),
            "description": "화면 없이 소리만 추출합니다 (음악, 팟캐스트용)."
        })

    return {
        "title": title,
        "thumbnail": thumbnail,
        "formats": formats
    }

@router.get("/download-token")
async def get_download_token(current_user: models.User = Depends(get_current_active_user)):
    """
    Generates a short-lived download token for an authenticated user.
    """
    token = create_download_token(current_user.username)
    return {"download_token": token}

class CookieData(BaseModel):
    content: str

@router.post("/cookies")
async def save_cookies(data: CookieData, current_user: models.User = Depends(get_current_active_user)):
    cookie_file = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(data.content)
    return {"message": "Cookies saved successfully"}

@router.delete("/cookies")
async def delete_cookies(current_user: models.User = Depends(get_current_active_user)):
    cookie_file = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
    if os.path.exists(cookie_file):
        os.remove(cookie_file)
    return {"message": "Cookies deleted successfully"}

@router.get("/cookies/status")
async def check_cookies_status(current_user: models.User = Depends(get_current_active_user)):
    cookie_file = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
    return {"has_cookies": os.path.exists(cookie_file)}

class JobStatus(BaseModel):
    id: str
    status: str  # "starting", "downloading", "merging", "ready", "error"
    progress: float
    message: str

# In-memory store for active download jobs
download_jobs = {}

@router.post("/prepare-download")
@limiter.limit("5/minute")
async def prepare_download(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Query(..., description="A short-lived download token"),
    url: str = Query(..., description="The URL of the video"),
    format_id: str = Query(..., description="The format ID to download"),
    current_user: models.User = Depends(get_current_user_from_token_query)
):
    """
    Initiates a background download job on the server.
    Returns a job_id that the client can poll for progress.
    """
    job_id = str(uuid.uuid4())
    download_jobs[job_id] = {
        "id": job_id,
        "status": "starting",
        "progress": 0.0,
        "message": "서버 다운로드 준비 중...",
        "filepath": None,
        "filename": None
    }
    
    background_tasks.add_task(process_download_job, job_id, url, format_id, current_user.username)
    return {"job_id": job_id}

@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, current_user: models.User = Depends(get_current_active_user)):
    """
    Returns the current status of a download job.
    """
    job = download_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

def process_download_job(job_id: str, url: str, format_id: str, username: str):
    job = download_jobs.get(job_id)
    if not job:
        return
        
    try:
        cookie_file = os.path.join(COOKIES_DIR, f"{username}.txt")
        
        # 1. Get title
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'http_headers': {'User-Agent': USER_AGENT}
        }
        if os.path.exists(cookie_file):
            ydl_opts_info['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')

        # 2. Setup progress hook
        def progress_hook(d):
            if d['status'] == 'downloading':
                progress_str = d.get('_percent_str', '0%').strip()
                progress_str = re.sub(r'\x1b\[[0-9;]*m', '', progress_str)
                progress_str = progress_str.replace('%', '')
                try:
                    p = float(progress_str)
                    job['progress'] = p
                    job['status'] = 'downloading'
                    job['message'] = f"서버로 다운로드 중... ({p:.1f}%)"
                except ValueError:
                    pass
            elif d['status'] == 'finished':
                job['progress'] = 100.0
                job['status'] = 'merging'
                job['message'] = "다운로드 완료! 고화질 병합 중 (시간이 소요될 수 있습니다)..."

        # Generate temp filename
        temp_id = str(uuid.uuid4())
        output_template = os.path.join(DOWNLOAD_DIR, f"{temp_id}.%(ext)s")

        ydl_opts = {
            'format': f"{format_id}+bestaudio/{format_id}",
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'http_headers': {'User-Agent': USER_AGENT}
        }
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'requested_downloads' in info and len(info['requested_downloads']) > 0:
                final_filepath = info['requested_downloads'][0]['filepath']
            else:
                final_filepath = ydl.prepare_filename(info)
                
        if not final_filepath or not os.path.exists(final_filepath):
            raise Exception("Downloaded file could not be found.")

        ext = os.path.splitext(final_filepath)[1].lstrip('.') or 'mp4'
        safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip() or "download"
        client_filename = f"{safe_title}.{ext}"

        job['filepath'] = final_filepath
        job['filename'] = client_filename
        job['status'] = 'ready'
        job['message'] = "준비 완료! 기기로 전송을 시작합니다."

    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg or "cookies" in error_msg.lower() or "Requested format is not available" in error_msg:
            job['status'] = 'error'
            job['message'] = "COOKIE_ERROR"
        else:
            job['status'] = 'error'
            job['message'] = f"오류 발생: {error_msg}"

@router.get("/download-file/{job_id}")
@limiter.limit("5/minute")
async def download_file(
    request: Request,
    job_id: str,
    token: str = Query(..., description="A short-lived download token"),
    current_user: models.User = Depends(get_current_user_from_token_query)
):
    """
    Transfers the completed file to the user and cleans up the temporary file and job.
    """
    job = download_jobs.get(job_id)
    if not job or job['status'] != 'ready':
        raise HTTPException(status_code=400, detail="File is not ready or job does not exist.")

    final_filepath = job['filepath']
    client_filename = job['filename']
    encoded_filename = urllib.parse.quote(client_filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }

    def cleanup():
        try:
            if os.path.exists(final_filepath):
                os.remove(final_filepath)
            if job_id in download_jobs:
                del download_jobs[job_id]
        except Exception:
            pass

    return FileResponse(
        path=final_filepath,
        filename=client_filename,
        media_type="application/octet-stream",
        headers=headers,
        background=BackgroundTask(cleanup)
    )
