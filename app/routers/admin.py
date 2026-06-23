from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app import schemas, models, security
from app.database import get_db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(security.get_current_admin_user)]
)

@router.get("/users", response_model=List[schemas.UserResponse])
async def get_pending_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.status == "pending"))
    users = result.scalars().all()
    return users

@router.patch("/users/{user_id}/approve", response_model=schemas.UserResponse)
async def approve_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status == "approved":
        raise HTTPException(status_code=400, detail="User is already approved")

    user.status = "approved"
    await db.commit()
    await db.refresh(user)
    return user
