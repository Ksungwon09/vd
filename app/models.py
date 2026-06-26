from sqlalchemy import Boolean, Column, Integer, String
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, index=True, nullable=True)   # email for OAuth users
    password_hash = Column(String, nullable=True)                            # null for OAuth users
    role          = Column(String, default="user")     # 'user' | 'admin'
    status        = Column(String, default="approved") # auto-approved for OAuth

    # ── Google OAuth2 ──────────────────────────────────────────────────────────
    google_id            = Column(String, unique=True, nullable=True, index=True)
    nickname             = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)  # AES-256-GCM encrypted
    auth_provider        = Column(String, default="google")  # 'local' | 'google'
    needs_nickname       = Column(Boolean, default=False)
