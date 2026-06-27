from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    verify_salted_password,
)
from src.api.dependencies import get_db, get_current_user
from src.infrastructure.database.models.user import User, LoginHistory

router = APIRouter()


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value,
        "requires_password_change": current_user.requires_password_change,
    }
