from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "default_secret_key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    initial_admin_username: str = "admin"
    database_url: str = "sqlite+aiosqlite:///./data/vdownloader.db"
    cookie_encryption_key: str = "n5x8oXYl8HrUFCwuYrOqtE5Cutsxxyb7B5M5fQ9NMhY="
    class Config:
        env_file = ".env"

settings = Settings()
