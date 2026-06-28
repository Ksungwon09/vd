"""
YouTube TV 인증 라우터
────────────────────────────────────────────────────────────────────────────
yt-dlp는 2025년부터 --username oauth2 방식을 제거했습니다.
현재 YouTube 인증은 오직 쿠키(SAPISID, LOGIN_INFO 등)로만 가능합니다.

Google OAuthLogin → MergeSession 플로우를 통해 실제 YouTube 세션 쿠키를 획득합니다.
이 방식은 Chrome 브라우저가 Google 로그인 시 실제로 사용하는 메커니즘입니다.

흐름:
  1. POST /video/tv-auth/fetch   → OAuthLogin → MergeSession → YouTube 쿠키 획득 → 저장
  2. GET  /video/tv-auth/status  → TV 인증 쿠키 존재 여부 반환
  3. DELETE /video/tv-auth       → 저장된 TV 인증 쿠키 삭제
"""

import os
import time
import urllib.parse
from contextlib import contextmanager
from typing import Optional, Tuple

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

# Chrome 을 흉내낸 User-Agent (YouTube 봇 감지 회피)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ── Google OAuthLogin → MergeSession 플로우 ─────────────────────────────────

async def _fetch_youtube_cookies_via_oauth(
    access_token: str,
) -> Tuple[dict, dict]:
    """
    Chrome 브라우저의 Google 로그인 메커니즘을 재현합니다.

    Steps:
      1. OAuthLogin  → uberauth 토큰 획득
      2. MergeSession → 리다이렉트 체인 수동 추적, 각 도메인 쿠키 수집
      3. YouTube 방문 → LOGIN_INFO 등 YouTube 전용 쿠키 수집

    Returns:
      (youtube_cookies, google_cookies) — 도메인별 딕셔너리
    """
    youtube_cookies: dict = {}
    google_cookies: dict  = {}

    try:
        # follow_redirects=False: 리다이렉트를 수동으로 추적해 각 도메인 쿠키 수집
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=30,
            headers={"User-Agent": _UA},
        ) as client:

            # ── Step 1: OAuthLogin ──────────────────────────────────────────
            uber_resp = await client.get(
                "https://accounts.google.com/accounts/OAuthLogin",
                params={"source": "ChromiumBrowser", "issueuberauth": "1"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            print(f"[tv-auth] OAuthLogin status={uber_resp.status_code}")

            if uber_resp.status_code != 200:
                print(f"[tv-auth] OAuthLogin failed: {uber_resp.text[:400]}")
                return youtube_cookies, google_cookies

            uberauth = uber_resp.text.strip()
            _merge_cookies(google_cookies, uber_resp, "google.com")
            print(f"[tv-auth] uberauth len={len(uberauth)}")

            # ── Step 2: MergeSession (수동 리다이렉트 추적) ─────────────────
            current_url = (
                "https://accounts.google.com/MergeSession?"
                + urllib.parse.urlencode({
                    "ubr":       "1",
                    "uberauth":  uberauth,
                    "continue":  "https://www.youtube.com/",
                })
            )

            for hop in range(12):
                # 현재 쿠키 풀 — 도메인에 따라 적절한 쿠키 선택
                if "youtube.com" in current_url:
                    req_cookies = youtube_cookies
                else:
                    req_cookies = google_cookies

                resp = await client.get(current_url, cookies=req_cookies)
                print(f"[tv-auth] hop={hop} url={current_url[:80]} status={resp.status_code} cookies={list(resp.cookies.keys())}")

                # 쿠키 수집
                if "youtube.com" in current_url:
                    _merge_cookies(youtube_cookies, resp, "youtube.com")
                else:
                    _merge_cookies(google_cookies, resp, "google.com")

                # 리다이렉트 처리
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location", "")
                    if not location:
                        break
                    if not location.startswith("http"):
                        location = urllib.parse.urljoin(current_url, location)
                    current_url = location
                else:
                    break

            print(f"[tv-auth] After MergeSession — google={list(google_cookies.keys())} youtube={list(youtube_cookies.keys())}")

            # ── Step 3: YouTube 방문 → LOGIN_INFO 등 수집 ──────────────────
            # Google 계정 쿠키 중 YouTube에서도 유효한 것들을 함께 전달
            combined = {**youtube_cookies}
            # SAPISID 가 Google 쪽에만 있으면 YouTube용으로도 복사
            for key in ("SAPISID", "APISID", "SSID", "HSID", "SID",
                        "__Secure-1PAPISID", "__Secure-3PAPISID",
                        "__Secure-1PSID", "__Secure-3PSID"):
                if key in google_cookies and key not in combined:
                    combined[key] = google_cookies[key]

            if combined:
                yt_resp = await client.get(
                    "https://www.youtube.com/",
                    cookies=combined,
                )
                print(f"[tv-auth] YouTube visit status={yt_resp.status_code} new_cookies={list(yt_resp.cookies.keys())}")
                _merge_cookies(youtube_cookies, yt_resp, "youtube.com")
            else:
                # 쿠키 없이 방문해서 기본 쿠키만 수집
                yt_resp = await client.get("https://www.youtube.com/")
                _merge_cookies(youtube_cookies, yt_resp, "youtube.com")

    except Exception as exc:
        print(f"[tv-auth] Exception: {exc}")

    return youtube_cookies, google_cookies


def _merge_cookies(target: dict, response: httpx.Response, domain_hint: str) -> None:
    """응답의 Set-Cookie 헤더를 파싱하여 target 딕셔너리에 병합합니다."""
    for k, v in response.cookies.items():
        target[k] = v


# ── Netscape 쿠키 파일 생성 ───────────────────────────────────────────────────

def _cookies_to_netscape(
    youtube_cookies: dict,
    google_cookies: dict,
) -> str:
    """
    yt-dlp 가 읽을 수 있는 Netscape HTTP Cookie File 포맷으로 변환합니다.

    yt-dlp 는 `https://www.youtube.com` 기준으로 쿠키를 필터링하므로
    `.youtube.com` 도메인 항목만 실제로 사용됩니다.
    단, Google 쪽에만 존재하는 인증 쿠키(SAPISID 등)는 `.youtube.com` 으로도 복사합니다.
    """
    lines = ["# Netscape HTTP Cookie File"]
    expiry = str(int(time.time()) + 365 * 24 * 3600)  # 1년

    AUTH_KEYS = {
        "SAPISID", "APISID", "SSID", "HSID", "SID",
        "__Secure-1PAPISID", "__Secure-3PAPISID",
        "__Secure-1PSID", "__Secure-3PSID",
        "LOGIN_INFO",
    }

    written = set()

    def _add(domain: str, name: str, value: str):
        if not value or (domain, name) in written:
            return
        secure = "TRUE" if (name.startswith("__Secure") or name.startswith("__Host")) else "FALSE"
        lines.append(f"{domain}\tTRUE\t/\t{secure}\t{expiry}\t{name}\t{value}")
        written.add((domain, name))

    # YouTube 도메인 쿠키 (yt-dlp 가 직접 읽음)
    for name, value in youtube_cookies.items():
        _add(".youtube.com", name, value)

    # Google 도메인 인증 쿠키 → YouTube 도메인으로도 복사
    for name, value in google_cookies.items():
        if name in AUTH_KEYS:
            _add(".youtube.com", name, value)  # YouTube용
        _add(".google.com", name, value)        # Google용 (일부 yt-dlp 요청에서 사용)

    return "\n".join(lines) + "\n"


# ── 파일 경로 헬퍼 ───────────────────────────────────────────────────────────

def get_tv_cookie_path(user_id: int) -> str:
    return os.path.join(COOKIES_DIR, f"tv_{user_id}.txt")


def has_tv_cookies(user_id: int) -> bool:
    path = get_tv_cookie_path(user_id)
    return os.path.exists(path) and os.path.getsize(path) > 50


@contextmanager
def temporary_tv_cookie(user_id: int):
    """TV 인증 쿠키 파일이 있으면 경로를 yield, 없으면 None을 yield합니다."""
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
    저장된 Google OAuth2 refresh_token으로 YouTube 세션 쿠키를 획득·저장합니다.

    Google OAuthLogin → MergeSession 플로우를 사용하여 실제 인증 쿠키(SAPISID, LOGIN_INFO)를
    획득합니다. 이는 Chrome 브라우저가 사용하는 것과 동일한 메커니즘입니다.
    """
    if not current_user.google_refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google 계정이 연결되지 않았습니다. Google로 로그인해주세요.",
        )

    # ── refresh_token → access_token ────────────────────────────────────────
    refresh_token = security.decrypt_token(current_user.google_refresh_token)
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
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

    # ── OAuthLogin → MergeSession → YouTube 쿠키 획득 ──────────────────────
    youtube_cookies, google_cookies = await _fetch_youtube_cookies_via_oauth(access_token)

    all_cookies = {**youtube_cookies}
    # Google 인증 쿠키도 포함 (yt-dlp 가 .google.com 쿠키도 참조할 수 있음)
    for k in ("SAPISID", "APISID", "__Secure-1PAPISID", "__Secure-3PAPISID", "LOGIN_INFO"):
        if k in google_cookies and k not in all_cookies:
            all_cookies[k] = google_cookies[k]

    if not all_cookies:
        raise HTTPException(
            status_code=502,
            detail=(
                "YouTube 쿠키를 전혀 받지 못했습니다. "
                "Google 계정 권한을 확인하거나 재로그인 후 다시 시도해주세요."
            ),
        )

    # ── 인증 수준 판단 ─────────────────────────────────────────────────────
    has_sapisid = bool(
        all_cookies.get("SAPISID")
        or all_cookies.get("__Secure-1PAPISID")
        or all_cookies.get("__Secure-3PAPISID")
        or google_cookies.get("SAPISID")
        or google_cookies.get("__Secure-1PAPISID")
        or google_cookies.get("__Secure-3PAPISID")
    )
    has_login_info = bool(all_cookies.get("LOGIN_INFO") or youtube_cookies.get("LOGIN_INFO"))

    # ── Netscape 파일로 저장 ────────────────────────────────────────────────
    cookie_content = _cookies_to_netscape(youtube_cookies, google_cookies)
    path = get_tv_cookie_path(current_user.id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(cookie_content)

    # 응답 메시지
    if has_sapisid and has_login_info:
        auth_level = "full"
        message = "✅ 완전한 YouTube 인증 성공! SAPISID + LOGIN_INFO 쿠키를 획득했습니다."
    elif has_sapisid:
        auth_level = "partial"
        message = "⚠️ 부분 인증: SAPISID 획득. LOGIN_INFO 없음 — 일부 연령 제한 콘텐츠 접근 가능."
    else:
        auth_level = "session_only"
        message = (
            "⚠️ 세션 쿠키만 획득 (SAPISID 없음). 봇 감지 회피에는 도움되나 "
            "로그인 필요 콘텐츠는 Google 재로그인 후 재시도 필요."
        )

    return {
        "message":        message,
        "auth_level":     auth_level,
        "has_sapisid":    has_sapisid,
        "has_login_info": has_login_info,
        "youtube_cookies": list(youtube_cookies.keys()),
        "google_cookies":  list(google_cookies.keys()),
    }


# ── 2. TV 인증 상태 조회 ─────────────────────────────────────────────────────

@router.get("/status")
async def get_tv_auth_status(
    current_user: User = Depends(get_current_active_user),
):
    """TV 인증 쿠키 파일 존재 여부와 기본 정보를 반환합니다."""
    path = get_tv_cookie_path(current_user.id)
    exists = has_tv_cookies(current_user.id)
    mtime = int(os.path.getmtime(path)) if exists else None

    return {
        "has_tv_cookies": exists,
        "updated_at":     mtime,
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
