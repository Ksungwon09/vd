"""
Google OAuth2 인증 라우터
흐름:
  1. GET  /auth/google/login      → Google 동의 화면으로 리다이렉트
  2. GET  /auth/google/callback   → code 교환 → user 생성/조회 → JWT 발급
  3. POST /auth/refresh           → HttpOnly refresh_token 쿠키로 새 access_token 발급
  4. POST /auth/logout            → refresh_token 쿠키 삭제
  5. POST /auth/setup-nickname    → 신규 유저 닉네임 설정 (admin 닉네임 → 관리자 부여)
  6. GET  /auth/me                → 현재 유저 정보 반환
"""

import secrets
import urllib.parse
from typing import Optional

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import schemas, security
from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["oauth"])

# ── Google OAuth2 엔드포인트 ────────────────────────────────────────────────────
GOOGLE_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO    = "https://www.googleapis.com/oauth2/v2/userinfo"

# YouTube 접근 권한 포함 (yt-dlp Bearer 인증 시 활용)
GOOGLE_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube",
])


# ── 1. Google 로그인 시작 ─────────────────────────────────────────────────────

@router.get("/google/login")
async def google_login():
    """CSRF state 쿠키를 발급하고 Google 동의 화면으로 리다이렉트."""
    state = secrets.token_urlsafe(32)

    params = {
        "client_id":     settings.google_client_id,
        "redirect_uri":  settings.google_redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "state":         state,
        "access_type":   "offline",  # refresh_token 수령
        "prompt":        "consent",  # 항상 동의 화면 표시 → refresh_token 보장
    }
    auth_url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)

    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=300,  # 5분
    )
    return response


# ── 2. Google 콜백 처리 ───────────────────────────────────────────────────────

@router.get("/google/callback")
async def google_callback(
    code:        str = Query(...),
    state:       str = Query(...),
    oauth_state: Optional[str] = Cookie(None),
    db:          AsyncSession = Depends(get_db),
):
    """Google 인증 코드 수령 → 토큰 교환 → 유저 생성/조회 → 프론트로 리다이렉트."""

    # ── CSRF 검증 ────────────────────────────────────────────────────────────
    if not oauth_state or not secrets.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="CSRF 검증 실패 (state 불일치)")

    # ── Google 토큰 교환 ──────────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri":  settings.google_redirect_uri,
            "grant_type":    "authorization_code",
        })

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Google 토큰 교환 실패: {token_resp.text}")

    g_tokens         = token_resp.json()
    g_access_token   = g_tokens.get("access_token")
    g_refresh_token  = g_tokens.get("refresh_token")

    # ── Google 유저 정보 조회 ─────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {g_access_token}"},
        )

    if info_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Google 유저 정보 조회 실패")

    userinfo  = info_resp.json()
    google_id = userinfo.get("id")
    email     = userinfo.get("email", "")

    if not google_id:
        raise HTTPException(status_code=400, detail="Google ID를 받을 수 없습니다.")

    # ── DB에서 유저 조회 또는 생성 ────────────────────────────────────────────
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalars().first()
    needs_nickname = False

    if not user:
        # 최초 로그인 → 닉네임 설정 필요
        user = User(
            google_id     = google_id,
            username      = email,       # 이메일을 username으로 임시 사용
            password_hash = "",          # 기존 DB의 NOT NULL 제약조건 우회용
            auth_provider = "google",
            role          = "user",
            status        = "approved",  # 구글 로그인 유저는 자동 승인
            needs_nickname = True,
        )
        if g_refresh_token:
            user.google_refresh_token = security.encrypt_token(g_refresh_token)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        needs_nickname = True
    else:
        # 기존 유저 → refresh_token 갱신 (Google은 재동의 시에만 발급)
        if g_refresh_token:
            user.google_refresh_token = security.encrypt_token(g_refresh_token)
            await db.commit()

    # ── 앱 JWT 발급 ───────────────────────────────────────────────────────────
    token_data    = {"sub": user.google_id, "provider": "google"}
    access_token  = security.create_access_token(token_data)
    refresh_token = security.create_refresh_token(token_data)

    # ── 프론트엔드로 리다이렉트 ────────────────────────────────────────────────
    params = {"token": access_token}
    if needs_nickname:
        params["needs_nickname"] = "1"
    redirect_url = f"{settings.frontend_url}/auth/callback?" + urllib.parse.urlencode(params)

    response = RedirectResponse(url=redirect_url)
    # refresh_token → HttpOnly Secure 쿠키
    response.set_cookie(
        key      = "refresh_token",
        value    = refresh_token,
        httponly = True,
        secure   = True,
        samesite = "none",   # 프론트(8080)와 백엔드(443)가 다른 origin
        max_age  = settings.refresh_token_expire_days * 24 * 3600,
        path     = "/",
    )
    response.delete_cookie("oauth_state")
    return response


# ── 3. Access Token 갱신 ─────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_access_token(
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """HttpOnly refresh_token 쿠키로 새 access_token을 발급합니다."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="refresh_token 쿠키가 없습니다.")
    try:
        payload = pyjwt.decode(
            refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="refresh_token이 유효하지 않거나 만료됐습니다.")

    user = await security._lookup_user(payload, db)
    if not user:
        raise HTTPException(status_code=401, detail="유저를 찾을 수 없습니다.")

    token_data   = {"sub": payload["sub"], "provider": payload.get("provider", "google")}
    new_access   = security.create_access_token(token_data)
    return {"access_token": new_access, "token_type": "bearer"}


# ── 4. 로그아웃 ──────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(response: Response):
    """refresh_token 쿠키를 삭제합니다."""
    response.delete_cookie(key="refresh_token", path="/", samesite="none", secure=True)
    return {"message": "로그아웃 완료"}


# ── 5. 닉네임 설정 (최초 로그인 후 1회) ──────────────────────────────────────

@router.post("/setup-nickname", response_model=schemas.UserResponse)
async def setup_nickname(
    data:         schemas.NicknameSetup,
    current_user: User = Depends(security.get_current_user),  # needs_nickname 체크 안 함
    db:           AsyncSession = Depends(get_db),
):
    """
    최초 로그인 시 닉네임을 설정합니다.
    - 닉네임이 'admin'이고 아직 관리자가 없으면 → 관리자 역할 부여
    - 중복 닉네임 불가
    """
    nickname = data.nickname.strip()

    if len(nickname) < 2:
        raise HTTPException(status_code=400, detail="닉네임은 2자 이상이어야 합니다.")
    if len(nickname) > 20:
        raise HTTPException(status_code=400, detail="닉네임은 20자 이하여야 합니다.")

    # admin 닉네임 → 관리자 역할 (최초 1명만)
    if nickname.lower() == "admin":
        result = await db.execute(select(User).where(User.role == "admin"))
        existing_admin = result.scalars().first()
        if existing_admin and existing_admin.id != current_user.id:
            raise HTTPException(status_code=400, detail="관리자는 이미 존재합니다. 다른 닉네임을 사용해주세요.")
        current_user.role = "admin"

    # 중복 닉네임 검사
    result = await db.execute(
        select(User).where(User.nickname == nickname, User.id != current_user.id)
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")

    current_user.nickname      = nickname
    current_user.needs_nickname = False
    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── 6. 내 정보 ───────────────────────────────────────────────────────────────

@router.get("/me", response_model=schemas.UserResponse)
async def get_me(current_user: User = Depends(security.get_current_user)):
    """현재 로그인된 유저 정보 (닉네임 설정 전도 허용)."""
    return current_user
