import asyncio
import os
import shutil
import uuid
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
import re
import httpx
import yt_dlp
from app import models
from app.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from app.security import (
    get_current_active_user,
    create_download_token,
    get_current_user_from_token_query,
    encrypt_cookie,
    decrypt_cookie,
    decrypt_token,
)
from app.routers.tv_auth import temporary_tv_cookie, has_tv_cookies
import tempfile
from contextlib import contextmanager

# ── 설정 ──────────────────────────────────────────────────────────────────────

USER_AGENT   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DOWNLOAD_DIR = "downloads"
COOKIES_DIR  = "data/cookies"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR,  exist_ok=True)

router = APIRouter(prefix="/video", tags=["video"])


# ── 쿠키 헬퍼 (레거시 .enc 파일 — 하위 호환) ────────────────────────────────

@contextmanager
def temporary_decrypted_cookie(username: str):
    """암호화된 쿠키 파일을 임시 복호화하여 yt-dlp에 전달."""
    enc_file = os.path.join(COOKIES_DIR, f"{username}.enc")
    if not os.path.exists(enc_file):
        yield None
        return
    try:
        with open(enc_file, "rb") as f:
            encrypted_content = f.read()
        decrypted_content = decrypt_cookie(encrypted_content)
    except Exception as e:
        print(f"쿠키 복호화 실패 ({username}): {e}")
        yield None
        return

    fd, temp_path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(decrypted_content)
    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ── Google OAuth2 Access Token 갱신 ──────────────────────────────────────────

async def get_google_access_token(user: models.User) -> Optional[str]:
    """
    DB에 저장된 암호화 refresh_token으로 Google access_token을 갱신합니다.
    yt-dlp의 Authorization: Bearer 헤더에 사용됩니다.
    """
    if not user.google_refresh_token:
        return None
    try:
        refresh_token = decrypt_token(user.google_refresh_token)
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id":     settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
            })
        if resp.status_code == 200:
            return resp.json().get("access_token")
        print(f"Google token refresh 실패: {resp.text}")
    except Exception as e:
        print(f"Google token 갱신 오류: {e}")
    return None


# ── 영상 정보 조회 ────────────────────────────────────────────────────────────

@router.get("/info")
@limiter.limit("10/minute")
async def get_video_info(
    request:      Request,
    url:          str = Query(..., description="영상 URL"),
    current_user: models.User = Depends(get_current_active_user),
):
    """영상 메타데이터(제목, 썸네일, 포맷 목록) 조회."""

    user_id  = current_user.id
    username = current_user.username

    def extract_info():
        # ── 인증 우선순위: TV 쿠키 → 레거시 쿠키 → 미인증 ──────────────────
        with temporary_tv_cookie(user_id) as tv_cookie:
            with temporary_decrypted_cookie(username) as legacy_cookie:
                cookie_file = tv_cookie or legacy_cookie

                # TV 클라이언트를 1순위로, 쿠키 있으면 tv/web, 없으면 mweb/web
                if cookie_file:
                    player_clients = ["tv", "web", "mweb", "web_creator"]
                else:
                    player_clients = ["mweb", "web", "web_creator"]

                ydl_opts = {
                    "quiet":         True,
                    "no_warnings":   True,
                    "skip_download": True,
                    "format":        "all",
                    "extractor_args": {
                        "youtube": {"player_client": player_clients},
                        "youtubepot-bgutilhttp": {"base_url": ["http://pot-provider:4416"]},
                    },
                    "remote_components": ["ejs:github"],
                }
                if cookie_file:
                    ydl_opts["cookiefile"] = cookie_file

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.to_thread(extract_info)
        if not info:
            raise Exception("영상 정보를 가져올 수 없습니다.")
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg or "cookies" in error_msg.lower():
            raise HTTPException(status_code=403, detail="COOKIE_ERROR")
        if "Requested format is not available" in error_msg:
            raise HTTPException(status_code=403, detail="COOKIE_ERROR")
        raise HTTPException(status_code=400, detail=f"정보 조회 실패: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"정보 조회 실패: {str(e)}")

    title       = info.get("title", "Unknown Title")
    thumbnail   = info.get("thumbnail", "")
    raw_formats = info.get("formats", [])

    if not raw_formats:
        raise HTTPException(status_code=403, detail="COOKIE_ERROR")

    video_formats: dict = {}
    audio_formats: list = []

    for f in raw_formats:
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        height = f.get("height")

        # Audio-only format
        if vcodec == "none" and acodec != "none":
            audio_formats.append(f)
            continue
            
        # Fallback for missing vcodec/acodec but has resolution or height
        if vcodec is None and acodec is None:
            if f.get("resolution") == "audio only":
                audio_formats.append(f)
                continue

        # Video format
        if vcodec != "none":
            # If height is missing, try to parse from resolution (e.g. '1920x1080')
            if not height and f.get("resolution") and "x" in f.get("resolution"):
                try:
                    height = int(f.get("resolution").split("x")[1])
                except:
                    pass
            
            # If we still don't have height, use a fallback based on format_note or just 0
            if not height:
                height = 0

            def score(fmt):
                s = 0
                if fmt.get("ext") == "mp4":  s += 100
                vc = fmt.get("vcodec", "") or ""
                if vc.startswith("avc1"):    s += 50
                elif vc.startswith("vp09"): s += 20
                return s

            if height not in video_formats or score(f) >= score(video_formats[height]):
                video_formats[height] = f

    formats = []
    
    # If our filtering somehow rejected everything but raw_formats has data,
    # just dump a few raw formats so the user can download SOMETHING.
    if not video_formats and not audio_formats and raw_formats:
        for f in raw_formats[-3:]:
            formats.append({
                "format_id":   f.get("format_id"),
                "resolution":  f.get("format_note") or f.get("resolution") or "Unknown",
                "ext":         f.get("ext", "mp4"),
                "filesize":    f.get("filesize") or f.get("filesize_approx"),
                "description": "기본 제공 포맷",
            })
    else:
        for h in sorted(video_formats.keys(), reverse=True):
            vf = video_formats[h]
            if   h >= 2160: label = f"4K 초고화질 ({h}p)"
            elif h >= 1440: label = f"2K 고화질 ({h}p)"
            elif h >= 1080: label = f"FHD 표준화질 ({h}p)"
            elif h >= 720:  label = f"HD 일반화질 ({h}p)"
            elif h > 0:     label = f"SD 저화질 ({h}p)"
            else:           label = vf.get("format_note") or vf.get("resolution") or "알 수 없는 화질"
    
            formats.append({
                "format_id":   vf.get("format_id"),
                "resolution":  label,
                "ext":         "mp4",
                "filesize":    vf.get("filesize") or vf.get("filesize_approx"),
                "description": "영상과 소리가 포함된 파일입니다.",
            })
    
        if audio_formats:
            best_audio = audio_formats[-1]
            formats.append({
                "format_id":   best_audio.get("format_id"),
                "resolution":  "음원 전용 (최고 음질)",
                "ext":         best_audio.get("ext", "m4a"),
                "filesize":    best_audio.get("filesize") or best_audio.get("filesize_approx"),
                "description": "화면 없이 소리만 추출합니다 (음악, 팟캐스트용).",
            })

    return {"title": title, "thumbnail": thumbnail, "formats": formats}


# ── 다운로드 토큰 발급 ────────────────────────────────────────────────────────

@router.get("/download-token")
async def get_download_token(current_user: models.User = Depends(get_current_active_user)):
    """단기(5분) 다운로드 토큰 발급."""
    identifier = current_user.google_id or current_user.username or ""
    token = create_download_token(identifier, current_user.auth_provider)
    return {"download_token": token}


# ── 쿠키 관리 (레거시 지원) ──────────────────────────────────────────────────

class CookieData(BaseModel):
    content: str


@router.post("/cookies")
async def save_cookies(
    data: CookieData,
    current_user: models.User = Depends(get_current_active_user),
):
    """yt-dlp 쿠키 파일 업로드 (선택 사항, 레거시 또는 비공개 영상용)."""
    cookie_file = os.path.join(COOKIES_DIR, f"{current_user.username}.enc")
    encrypted_data = encrypt_cookie(data.content)
    with open(cookie_file, "wb") as f:
        f.write(encrypted_data)
    old = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
    if os.path.exists(old):
        os.remove(old)
    return {"message": "쿠키가 저장됐습니다."}


@router.delete("/cookies")
async def delete_cookies(current_user: models.User = Depends(get_current_active_user)):
    for ext in (".enc", ".txt"):
        path = os.path.join(COOKIES_DIR, f"{current_user.username}{ext}")
        if os.path.exists(path):
            os.remove(path)
    return {"message": "쿠키가 삭제됐습니다."}


@router.get("/cookies/status")
async def check_cookies_status(current_user: models.User = Depends(get_current_active_user)):
    enc = os.path.join(COOKIES_DIR, f"{current_user.username}.enc")
    txt = os.path.join(COOKIES_DIR, f"{current_user.username}.txt")
    has_legacy_cookie = os.path.exists(enc) or os.path.exists(txt)
    has_google_auth   = bool(current_user.google_refresh_token)
    tv_cookies        = has_tv_cookies(current_user.id)

    if tv_cookies:
        auth_method = "tv_oauth"
    elif has_legacy_cookie:
        auth_method = "cookie"
    else:
        auth_method = "none"

    return {
        "has_cookies":     has_legacy_cookie,
        "has_google_auth": has_google_auth,
        "has_tv_cookies":  tv_cookies,
        "auth_method":     auth_method,
    }


# ── 다운로드 작업 ─────────────────────────────────────────────────────────────

class JobStatus(BaseModel):
    id:       str
    status:   str   # starting | downloading | merging | ready | error
    progress: float
    message:  str


download_jobs: dict = {}


@router.post("/prepare-download")
@limiter.limit("5/minute")
async def prepare_download(
    request:          Request,
    background_tasks: BackgroundTasks,
    token:            str = Query(..., description="단기 다운로드 토큰"),
    url:              str = Query(..., description="영상 URL"),
    format_id:        str = Query(..., description="포맷 ID"),
    current_user:     models.User = Depends(get_current_user_from_token_query),
):
    """백그라운드 다운로드 작업을 시작하고 job_id를 반환합니다."""
    job_id = str(uuid.uuid4())
    download_jobs[job_id] = {
        "id":       job_id,
        "status":   "starting",
        "progress": 0.0,
        "message":  "서버 다운로드 준비 중...",
        "filepath": None,
        "filename": None,
    }
    background_tasks.add_task(
        process_download_job,
        job_id, url, format_id,
        current_user.username,
        current_user.id,   # TV 쿠키 조회용 user_id 추가
    )
    return {"job_id": job_id}


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(
    job_id:       str,
    current_user: models.User = Depends(get_current_active_user),
):
    job = download_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return job


def process_download_job(
    job_id:   str,
    url:      str,
    format_id: str,
    username: str,
    user_id:  int,
):
    """동기 백그라운드 작업: yt-dlp로 영상 다운로드."""
    job = download_jobs.get(job_id)
    if not job:
        return

    try:
        # ── 인증 우선순위: TV 쿠키 → 레거시 쿠키 → 미인증 ──────────────────
        with temporary_tv_cookie(user_id) as tv_cookie:
            with temporary_decrypted_cookie(username) as legacy_cookie:
                cookie_file = tv_cookie or legacy_cookie

                # TV 클라이언트 우선, 쿠키 있을 때 tv 포함
                if cookie_file:
                    player_clients = ["tv", "web", "mweb", "web_creator"]
                else:
                    player_clients = ["mweb", "web", "web_creator"]

                base_extractor_args = {
                    "youtube": {"player_client": player_clients},
                    "youtubepot-bgutilhttp": {"base_url": ["http://pot-provider:4416"]},
                }

                # 1. 제목 조회
                ydl_opts_info = {
                    "quiet":         True,
                    "no_warnings":   True,
                    "skip_download": True,
                    "extractor_args": base_extractor_args,
                    "remote_components": ["ejs:github"],
                }
                if cookie_file:
                    ydl_opts_info["cookiefile"] = cookie_file

                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info  = ydl.extract_info(url, download=False)
                    title = info.get("title", "video")

                # 2. 진행률 훅
                def progress_hook(d):
                    if d["status"] == "downloading":
                        raw = d.get("_percent_str", "0%").strip()
                        raw = re.sub(r"\x1b\[[0-9;]*m", "", raw).replace("%", "")
                        try:
                            p = float(raw)
                            job["progress"] = p
                            job["status"]   = "downloading"
                            job["message"]  = f"서버로 다운로드 중... ({p:.1f}%)"
                        except ValueError:
                            pass
                    elif d["status"] == "finished":
                        job["progress"] = 100.0
                        job["status"]   = "merging"
                        job["message"]  = "다운로드 완료! 고화질 병합 중..."

                # 3. 다운로드
                temp_id         = str(uuid.uuid4())
                output_template = os.path.join(DOWNLOAD_DIR, f"{temp_id}.%(ext)s")

                ydl_opts = {
                    "format":              f"{format_id}+bestaudio/{format_id}",
                    "outtmpl":             output_template,
                    "merge_output_format": "mp4",
                    "quiet":               True,
                    "no_warnings":         True,
                    "progress_hooks":      [progress_hook],
                    "extractor_args":      base_extractor_args,
                    "remote_components":   ["ejs:github"],
                }
                if cookie_file:
                    ydl_opts["cookiefile"] = cookie_file

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    dl_info = ydl.extract_info(url, download=True)
                    if "requested_downloads" in dl_info and dl_info["requested_downloads"]:
                        final_filepath = dl_info["requested_downloads"][0]["filepath"]
                    else:
                        final_filepath = ydl.prepare_filename(dl_info)

                if not final_filepath or not os.path.exists(final_filepath):
                    raise Exception("다운로드된 파일을 찾을 수 없습니다.")

                ext             = os.path.splitext(final_filepath)[1].lstrip(".") or "mp4"
                safe_title      = "".join(c for c in title if c.isalnum() or c in " ._-").strip() or "download"
                client_filename = f"{safe_title}.{ext}"

                job["filepath"] = final_filepath
                job["filename"] = client_filename
                job["status"]   = "ready"
                job["message"]  = "준비 완료! 기기로 전송을 시작합니다."

    except Exception as e:
        error_msg = str(e)
        is_cookie_error = any(kw in error_msg for kw in [
            "Sign in to confirm", "cookies", "Requested format is not available",
            "LOGIN_REQUIRED", "This video is only available",
        ])
        job["status"]  = "error"
        job["message"] = "COOKIE_ERROR" if is_cookie_error else f"오류 발생: {error_msg}"


@router.get("/download-file/{job_id}")
@limiter.limit("5/minute")
async def download_file(
    request:      Request,
    job_id:       str,
    token:        str = Query(..., description="단기 다운로드 토큰"),
    current_user: models.User = Depends(get_current_user_from_token_query),
):
    """완료된 파일을 클라이언트로 전송하고 임시 파일과 작업을 정리합니다."""
    job = download_jobs.get(job_id)
    if not job or job["status"] != "ready":
        raise HTTPException(status_code=400, detail="파일이 준비되지 않았거나 작업이 없습니다.")

    final_filepath  = job["filepath"]
    client_filename = job["filename"]
    encoded_filename = urllib.parse.quote(client_filename)

    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}

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
        background=BackgroundTask(cleanup),
    )
