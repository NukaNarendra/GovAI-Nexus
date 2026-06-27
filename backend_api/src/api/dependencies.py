from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from src.core.config import settings
from src.core.security import decode_token
from src.infrastructure.database.session import db_manager
from src.infrastructure.database.models.user import User, UserRole
from src.infrastructure.cache.redis_client import RedisCacheManager
from src.infrastructure.llm_provider.groq_client import GroqClientManager

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

redis_manager = RedisCacheManager(redis_url=settings.REDIS_URL)

llm_manager = GroqClientManager(
    api_key=settings.GROQ_API_KEY, default_model=settings.DEFAULT_LLM_MODEL
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session


async def get_redis() -> RedisCacheManager:
    return redis_manager


async def get_llm_client() -> GroqClientManager:
    return llm_manager


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except ValueError:
        raise credentials_exception

    query = select(User).where(User.id == user_id, User.is_deleted == False)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account"
        )
    if user.is_locked_out():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked",
        )

    return user


async def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


async def get_current_compliance_officer(
    current_user: User = Depends(get_current_user),
) -> User:
    allowed_roles = {
        UserRole.SYSTEM_ADMIN,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.RISK_ANALYST,
    }
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires compliance officer privileges",
        )
    return current_user
