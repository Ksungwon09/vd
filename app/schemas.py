from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: Optional[str] = None
    nickname: Optional[str] = None
    role: str
    status: str
    auth_provider: str = "google"
    needs_nickname: bool = False

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class NicknameSetup(BaseModel):
    nickname: str


class UserUpdateStatus(BaseModel):
    status: str


class UserUpdateRole(BaseModel):
    role: str
