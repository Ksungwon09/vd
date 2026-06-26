import hashlib
import os
import base64
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models import User


# ── Password ──────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ── Fernet (legacy yt-dlp cookie encryption — backward compat) ────────────────

fernet = Fernet(settings.cookie_encryption_key.encode())


def encrypt_cookie(content: str) -> bytes:
    return fernet.encrypt(content.encode("utf-8"))


def decrypt_cookie(encrypted_content: bytes) -> str:
    return fernet.decrypt(encrypted_content).decode("utf-8")


# ── AES-256-GCM (Google OAuth2 refresh token storage) ────────────────────────

def _aes_key() -> bytes:
    """Derive a 32-byte key from JWT secret via SHA-256."""
    return hashlib.sha256(settings.jwt_secret.encode()).digest()


def encrypt_token(data: str) -> str:
    """AES-256-GCM encrypt.  Returns base64(nonce + ciphertext + tag)."""
    key = _aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)                          # 96-bit random nonce
    ct = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def decrypt_token(encrypted_data: str) -> str:
    """AES-256-GCM decrypt."""
    key = _aes_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted_data)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_download_token(identifier: str, provider: str = "google") -> str:
    expire = datetime.utcnow() + timedelta(minutes=5)
    to_encode = {"sub": identifier, "exp": expire, "type": "download", "provider": provider}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ── Shared user-lookup (google_id OR username) ────────────────────────────────

async def _lookup_user(payload: dict, db: AsyncSession) -> Optional[User]:
    sub: str = payload.get("sub", "")
    provider: str = payload.get("provider", "local")
    if not sub:
        return None
    if provider == "google":
        result = await db.execute(select(User).where(User.google_id == sub))
    else:
        result = await db.execute(select(User).where(User.username == sub))
    return result.scalars().first()


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        token_type = payload.get("type")
        # Accept access tokens OR tokens without explicit type (legacy)
        if token_type not in ("access", None):
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await _lookup_user(payload, db)
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_from_token_query(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> User:
    """For download endpoints where the token arrives as a query parameter."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "download":
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await _lookup_user(payload, db)
    if user is None or user.status != "approved":
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.status != "approved":
        raise HTTPException(status_code=403, detail="Not an approved user")
    if current_user.needs_nickname:
        raise HTTPException(status_code=403, detail="NEEDS_NICKNAME")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user
