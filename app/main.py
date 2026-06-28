import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine, Base
from app.routers import auth, admin, video
from app.routers import oauth   # Google OAuth2
from app.routers import tv_auth  # YouTube TV 인증 쿠키


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Private V-Downloader", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "https://video.igise.kro.kr",
        "https://video.igise.kro.kr:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# oauth 라우터를 auth보다 먼저 등록 (prefix 충돌 방지)
app.include_router(oauth.router)    # /auth/google/*, /auth/refresh, /auth/logout, /auth/me
app.include_router(auth.router)     # /auth/login (로컬 로그인)
app.include_router(admin.router)
app.include_router(video.router)
app.include_router(tv_auth.router)  # /video/tv-auth/*


@app.get("/")
async def root():
    return {"message": "Private V-Downloader API"}
