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
async def get_all_users(db: AsyncSession = Depends(get_db)):
    """
    Returns all users for the admin dashboard.
    """
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users

@router.put("/users/{user_id}/status", response_model=schemas.UserResponse)
async def update_user_status(
    user_id: int, 
    status_update: schemas.UserUpdateStatus, 
    db: AsyncSession = Depends(get_db)
):
    """
    Updates a user's status (e.g., pending, approved, rejected).
    """
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = status_update.status
    await db.commit()
    await db.refresh(user)
    return user

@router.put("/users/{user_id}/role", response_model=schemas.UserResponse)
async def update_user_role(
    user_id: int, 
    role_update: schemas.UserUpdateRole, 
    db: AsyncSession = Depends(get_db)
):
    """
    Updates a user's role (e.g., admin, user).
    """
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role_update.role
    await db.commit()
    await db.refresh(user)
    return user

@router.patch("/users/{user_id}/approve", response_model=schemas.UserResponse)
async def approve_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Legacy approval endpoint for backward compatibility.
    """
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "approved"
    await db.commit()
    await db.refresh(user)
    return user
