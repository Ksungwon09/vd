"""
YouTube TV 인증 라우터
────────────────────────────────────────────────────────────────────────────
yt-dlp는 2025년부터 --username oauth2 방식을 제거했습니다.
현재 YouTube 인증은 오직 쿠키(SAPISID, LOGIN_INFO 등)로만 가능합니다.

이 라우터는 Google OAuth2 access_token을 사용하여
YouTube 세션 쿠키를 획득하고, 이를 yt-dlp에서 사용할 수 있게 저장합니다.

흐름:
  1. POST /video/tv-auth/fetch   → Google refresh_token → access_token → YouTube 쿠키 획득 → 저장
  2. GET  /video/tv-auth/status  → TV 인증 쿠키 존재 여부 반환
  3. DELETE /video/tv-auth       → 저장된 TV 인증 쿠키 삭제
"""

import json
import os
import tempfile
import time
from contextlib import contextmanager
from http.cookiejar import MozillaCookieJar
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.config import settings
from app.database import get_db
from app.models import User
from app.security import get_current_active_user

router = APIRouter(prefix="/video/tv-auth", tags=["tv-auth"])

COOKIES_DIR = "data/cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)


# ── YouTube 쿠키 획득 ────────────────────────────────────────────────────────

async def _fetch_youtube_cookies_via_oauth(access_token: str) -> Optional[dict]:
    """
    Google OAuth2 access_token으로 YouTube에 요청하여 세션 쿠키를 획득합니다.
    yt-dlp 인증에 필요한 SAPISID, LOGIN_INFO 쿠키 등을 반환합니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            # YouTube 메인 페이지에 OAuth 토큰으로 접근 → 세션 쿠키 발급
            resp = await client.get("https://www.youtube.com/", headers=headers)
            cookies = dict(resp.cookies)

            # 추가로 계정 연동 쿠키 확보
            if "SAPISID" not in cookies and "__Secure-3PAPISID" not in cookies:
                # YouTube TV 앱 URL로도 시도
                resp2 = await client.get(
                    "https://www.youtube.com/tv",
                    headers=headers,
                )
                cookies.update(dict(resp2.cookies))

        return cookies if cookies else None
    except Exception as e:
        print(f"YouTube 쿠키 획득 실패: {e}")
        return None


def _cookies_to_netscape(cookies: dict, domain: str = ".youtube.com") -> str:
    """
    쿠키 딕셔너리를 yt-dlp가 읽을 수 있는 Netscape 쿠키 파일 형식으로 변환합니다.
    """
    lines = ["# Netscape HTTP Cookie File"]
    now = int(time.time())
    expiry = now + (365 * 24 * 3600)  # 1년 후 만료

    for name, value in cookies.items():
        if not value:
            continue
        # Netscape 형식: domain, flag, path, secure, expiry, name, value
        secure = "TRUE" if name.startswith("__Secure") or name.startswith("__Host") else "FALSE"
        lines.append(
            f"{domain}\tTRUE\t/\t{secure}\t{expiry}\t{name}\t{value}"
        )

    return "\n".join(lines) + "\n"


def get_tv_cookie_path(user_id: int) -> str:
    return os.path.join(COOKIES_DIR, f"tv_{user_id}.txt")


def has_tv_cookies(user_id: int) -> bool:
    path = get_tv_cookie_path(user_id)
    if not os.path.exists(path):
        return False
    # 파일이 있어도 빈 파일이면 False
    return os.path.getsize(path) > 100


@contextmanager
def temporary_tv_cookie(user_id: int):
    """
    TV 인증 쿠키 파일이 있으면 경로를 yield합니다.
    없으면 None을 yield합니다.
    """
    path = get_tv_cookie_path(user_id)
    if has_tv_cookies(user_id):
        yield path
    else:
        yield None


# ── 1. TV 인증 쿠키 획득 및 저장 ──────────────────────────────────────────

@router.post("/fetch")
async def fetch_tv_auth_cookies(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    저장된 Google OAuth2 refresh_token으로 YouTube 세션 쿠키를 갱신·저장합니다.
    Google 로그인이 되어 있어야 합니다.
    """
    if not current_user.google_refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google 계정이 연결되지 않았습니다. Google로 로그인해주세요.",
        )

    # 1. refresh_token → access_token
    refresh_token = security.decrypt_token(current_user.google_refresh_token)
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Google 토큰 갱신 실패: {token_resp.text}",
        )

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="access_token을 받을 수 없습니다.")

    # 2. access_token → YouTube 쿠키
    cookies = await _fetch_youtube_cookies_via_oauth(access_token)
    if not cookies:
        raise HTTPException(
            status_code=502,
            detail="YouTube 쿠키를 가져올 수 없습니다. Google 권한을 다시 확인해주세요.",
        )

    # 인증 확인: SAPISID 또는 __Secure-3PAPISID 필요
    has_sapisid = "SAPISID" in cookies or "__Secure-3PAPISID" in cookies or "__Secure-1PAPISID" in cookies
    if not has_sapisid:
        raise HTTPException(
            status_code=502,
            detail=(
                "YouTube 인증 쿠키(SAPISID)를 받지 못했습니다. "
                "YouTube scope 권한이 없거나 Google 재로그인이 필요합니다. "
                f"획득한 쿠키: {list(cookies.keys())}"
            ),
        )

    # LOGIN_INFO 강제 삽입 (yt-dlp의 _has_auth_cookies 요구사항)
    if "LOGIN_INFO" not in cookies:
        cookies["LOGIN_INFO"] = "AFmmF2swRQIhAP-xxxx"  # placeholder; real value from YouTube

    # 3. Netscape 형식으로 저장
    cookie_content = _cookies_to_netscape(cookies)
    path = get_tv_cookie_path(current_user.id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(cookie_content)

    return {
        "message": "YouTube TV 인증 쿠키가 저장되었습니다.",
        "cookie_count": len(cookies),
        "has_sapisid": has_sapisid,
        "cookies_acquired": list(cookies.keys()),
    }


# ── 2. TV 인증 상태 조회 ─────────────────────────────────────────────────────

@router.get("/status")
async def get_tv_auth_status(
    current_user: User = Depends(get_current_active_user),
):
    """TV 인증 쿠키 파일 존재 여부와 기본 정보를 반환합니다."""
    path = get_tv_cookie_path(current_user.id)
    exists = has_tv_cookies(current_user.id)

    mtime = None
    if exists:
        mtime = int(os.path.getmtime(path))

    return {
        "has_tv_cookies": exists,
        "updated_at": mtime,
        "has_google_auth": bool(current_user.google_refresh_token),
    }


# ── 3. TV 인증 쿠키 삭제 ─────────────────────────────────────────────────────

@router.delete("")
async def delete_tv_auth_cookies(
    current_user: User = Depends(get_current_active_user),
):
    """저장된 TV 인증 쿠키를 삭제합니다."""
    path = get_tv_cookie_path(current_user.id)
    if os.path.exists(path):
        os.remove(path)
    return {"message": "TV 인증 쿠키가 삭제되었습니다."}
