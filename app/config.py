from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT
    jwt_secret: str = "default_secret_key_please_change_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15   # short-lived access token
    refresh_token_expire_days: int = 30     # long-lived refresh token

    # DB
    database_url: str = "sqlite+aiosqlite:///./data/vdownloader.db"

    # Legacy cookie encryption key (Fernet / backward-compat)
    cookie_encryption_key: str = "n5x8oXYl8HrUFCwuYrOqtE5Cutsxxyb7B5M5fQ9NMhY="

    # Google OAuth2
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://video.igise.kro.kr/auth/google/callback"
    frontend_url: str = "https://video.igise.kro.kr"

    class Config:
        env_file = ".env"


settings = Settings()
