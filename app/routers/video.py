import asyncio
import sys
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import yt_dlp
from app import models
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from app.security import get_current_active_user, create_download_token, get_current_user_from_token_query

router = APIRouter(prefix="/video", tags=["video"])

# Generic modern browser User-Agent to avoid basic IP bans
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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
            'http_headers': {
                'User-Agent': USER_AGENT
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.to_thread(extract_info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract info: {str(e)}")

    title = info.get('title', 'Unknown Title')
    thumbnail = info.get('thumbnail', '')
    raw_formats = info.get('formats', [])

    formats = []
    for f in raw_formats:
        # Extract desired fields for each format
        formats.append({
            "format_id": f.get("format_id"),
            "resolution": f.get("format_note") or f.get("resolution") or f"{f.get('width', '')}x{f.get('height', '')}",
            "ext": f.get("ext"),
            "filesize": f.get("filesize") or f.get("filesize_approx")
        })

    return {
        "title": title,
        "thumbnail": thumbnail,
        "formats": formats
    }

async def yt_dlp_stream_generator(url: str, format_id: str):
    """
    Spawns yt-dlp as a subprocess to download the requested format to stdout.
    Reads stdout in chunks and yields them directly to the client.
    """
    # Build yt-dlp command
    # -f format_id: Select specific format
    # -o -: Output to stdout
    # --quiet, --no-warnings: Suppress logs to avoid corrupting the stdout stream
    # --add-header: Set custom User-Agent
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", format_id,
        "-o", "-",
        "--quiet",
        "--no-warnings",
        "--add-header", f"User-Agent:{USER_AGENT}",
        url
    ]

    # Run subprocess
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Read chunk by chunk from stdout
    chunk_size = 1024 * 64  # 64 KB chunks
    try:
        while True:
            chunk = await process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
    except asyncio.CancelledError:
        # If the client disconnects, terminate the yt-dlp process
        process.terminate()
        raise
    finally:
        # Ensure the process is cleaned up
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()

@router.get("/download-token")
async def get_download_token(current_user: models.User = Depends(get_current_active_user)):
    """
    Generates a short-lived download token for an authenticated user.
    """
    token = create_download_token(current_user.username)
    return {"download_token": token}

@router.get("/download")
@limiter.limit("5/minute")
async def download_video(
    request: Request,
    token: str = Query(..., description="A short-lived download token"),
    url: str = Query(..., description="The URL of the video"),
    format_id: str = Query(..., description="The format ID to download"),
    current_user: models.User = Depends(get_current_user_from_token_query)
):
    """
    Downloads the video as a stream directly to the client.
    Requires a valid short-lived download token.
    """
    # First, get the title to set the filename correctly
    def extract_title():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'http_headers': {
                'User-Agent': USER_AGENT
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'video'), info.get('ext', 'mp4')

    try:
        title, ext = await asyncio.to_thread(extract_title)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch video info: {str(e)}")

    # Sanitize title for filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
    if not safe_title:
        safe_title = "download"

    filename = f"{safe_title}.{ext}"

    # Encode filename for Content-Disposition header
    encoded_filename = urllib.parse.quote(filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }

    # Stream the response
    return StreamingResponse(
        yt_dlp_stream_generator(url, format_id),
        media_type="application/octet-stream",
        headers=headers
    )
