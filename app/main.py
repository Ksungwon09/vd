from contextlib import asynccontextmanager
from fastapi import FastAPI
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

app = FastAPI(title="Private V-Downloader", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(video.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Private V-Downloader API"}
