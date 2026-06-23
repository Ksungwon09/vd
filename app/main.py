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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup on shutdown
    await engine.dispose()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Private V-Downloader", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(video.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Private V-Downloader API"}
