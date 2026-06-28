import os
import json
import time
import uuid
import asyncio
import httpx
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from app import models
from app.security import get_current_active_user
from app.config import settings

# 암호화는 기본적으로 안해도 됨. 하지만 일관성을 위해 security.py의 encrypt/decrypt 활용 가능
from app.security import encrypt_token, decrypt_token

router = APIRouter(prefix="/tv-auth", tags=["TV-Auth"])

TV_OAUTH_DIR = os.path.join("data", "cookies")
os.makedirs(TV_OAUTH_DIR, exist_ok=True)

CLIENT_ID = '861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com'
CLIENT_SECRET = 'SboVhoG9s0rNafixCSGGKXAT'
SCOPES = 'https://gdata.youtube.com https://www.googleapis.com/auth/youtube'


class DeviceCodeResponse(BaseModel):
    user_code: str
    verification_url: str
    device_code: str
    interval: int

class PollRequest(BaseModel):
    device_code: str


def get_tv_oauth_path(user_id: int) -> str:
    return os.path.join(TV_OAUTH_DIR, f"tv_oauth_{user_id}.json")


@router.post("/device/code", response_model=DeviceCodeResponse)
async def request_device_code(current_user: models.User = Depends(get_current_active_user)):
    """TV 인증을 위한 기기 코드 발급"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://www.youtube.com/o/oauth2/device/code',
            json={
                'client_id': CLIENT_ID,
                'scope': SCOPES,
                'device_id': uuid.uuid4().hex,
                'device_model': 'ytlr::'
            },
            headers={'Content-Type': 'application/json'}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="기기 코드 발급에 실패했습니다.")
        data = resp.json()
        return DeviceCodeResponse(
            user_code=data['user_code'],
            verification_url=data['verification_url'],
            device_code=data['device_code'],
            interval=data['interval']
        )


@router.post("/device/poll")
async def poll_device_token(req: PollRequest, current_user: models.User = Depends(get_current_active_user)):
    """기기 코드로 토큰 발급 확인 (클라이언트가 interval 주기로 호출)"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://www.youtube.com/o/oauth2/token',
            json={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': req.device_code,
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
            },
            headers={'Content-Type': 'application/json'}
        )
        data = resp.json()
        
        if 'error' in data:
            if data['error'] == 'authorization_pending':
                return {"status": "pending"}
            else:
                raise HTTPException(status_code=400, detail=f"인증 오류: {data['error']}")
        
        # 성공 시 토큰 저장
        token_data = {
            'access_token': data['access_token'],
            'expires': datetime.now(timezone.utc).timestamp() + data['expires_in'],
            'refresh_token': data['refresh_token'],
            'token_type': data.get('token_type', 'Bearer')
        }
        
        # 암호화해서 저장
        encrypted = encrypt_token(json.dumps(token_data))
        path = get_tv_oauth_path(current_user.id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(encrypted)
            
        return {"status": "success", "message": "TV 인증이 완료되었습니다."}


# video.py 등에서 내부적으로 호출할 토큰 조회/갱신 함수
async def get_valid_tv_token(user_id: int) -> Optional[str]:
    path = get_tv_oauth_path(user_id)
    if not os.path.exists(path):
        return None
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            encrypted = f.read()
        token_data = json.loads(decrypt_token(encrypted))
        
        # 만료 1분 전이면 갱신
        if token_data['expires'] < datetime.now(timezone.utc).timestamp() + 60:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    'https://www.youtube.com/o/oauth2/token',
                    json={
                        'client_id': CLIENT_ID,
                        'client_secret': CLIENT_SECRET,
                        'refresh_token': token_data['refresh_token'],
                        'grant_type': 'refresh_token'
                    },
                    headers={'Content-Type': 'application/json'}
                )
                if resp.status_code != 200:
                    return None
                
                new_data = resp.json()
                token_data['access_token'] = new_data['access_token']
                token_data['expires'] = datetime.now(timezone.utc).timestamp() + new_data['expires_in']
                if 'refresh_token' in new_data:
                    token_data['refresh_token'] = new_data['refresh_token']
                
                encrypted_new = encrypt_token(json.dumps(token_data))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(encrypted_new)
                    
        return token_data['access_token']
    except Exception:
        return None

@router.delete("")
async def delete_tv_oauth(current_user: models.User = Depends(get_current_active_user)):
    """TV 인증 정보 삭제"""
    path = get_tv_oauth_path(current_user.id)
    if os.path.exists(path):
        os.remove(path)
    return {"message": "TV 인증 정보가 삭제되었습니다."}
