import asyncio, httpx, sys
sys.path.append('/home/ubuntu/vd')
from app.database import Base
from app.models import User
from app.security import decrypt_token
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

async def test():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.google_refresh_token != None))
        user = result.scalars().first()
        if not user:
            print('No user with google token')
            return
            
        refresh_token = decrypt_token(user.google_refresh_token)
        
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'client_id': settings.google_client_id,
                    'client_secret': settings.google_client_secret,
                    'refresh_token': refresh_token,
                    'grant_type': 'refresh_token',
                }
            )
            access_token = token_resp.json().get('access_token')
            print('Got access token:', access_token is not None)
            
            # Test Innertube API with Bearer token
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'X-YouTube-Client-Name': '1', # WEB
                'X-YouTube-Client-Version': '2.20240101.00.00',
            }
            # q2HoLuVQg-s is age restricted
            data = {
                'context': {
                    'client': {
                        'clientName': 'WEB',
                        'clientVersion': '2.20240101.00.00'
                    }
                },
                'videoId': 'q2HoLuVQg-s'
            }
            player_resp = await client.post(
                'https://www.youtube.com/youtubei/v1/player',
                headers=headers,
                json=data
            )
            print('Player status:', player_resp.status_code)
            playability = player_resp.json().get('playabilityStatus', {})
            print('Playability:', playability.get('status'), playability.get('reason'))

asyncio.run(test())
