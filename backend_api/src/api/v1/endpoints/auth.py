import os
import time
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Header,
    BackgroundTasks,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from pydantic import BaseModel, EmailStr, Field
import logging
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    verify_salted_password,
    hash_password_with_salt,
    generate_salt,
)
from src.api.dependencies import get_db, get_current_user, get_redis
from src.infrastructure.database.models.user import (
    User,
    LoginHistory,
    APIKey,
    APIKeyStatus,
)
from src.infrastructure.cache.redis_client import RedisCacheManager

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_context: Dict[str, Any]


class MFARequest(BaseModel):
    mfa_code: str = Field(..., min_length=6, max_length=6)
    device_id: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)
    confirm_new_password: str


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    allowed_ips: Optional[str] = None
    expiration_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    raw_key: Optional[str] = None
    status: str
    expires_at: Optional[datetime]
    created_at: datetime


class ActiveSessionResponse(BaseModel):
    session_id: str
    ip_address: str
    user_agent: str
    created_at: str
    last_active: str
    is_current: bool


async def _verify_ip_anomaly(db: AsyncSession, user_id: str, current_ip: str) -> bool:
    query = (
        select(LoginHistory.ip_address)
        .where(and_(LoginHistory.user_id == user_id, LoginHistory.status == "SUCCESS"))
        .order_by(LoginHistory.login_time.desc())
        .limit(5)
    )
    result = await db.execute(query)
    historical_ips = [row[0] for row in result.all()]
    if not historical_ips:
        return False
    return current_ip not in historical_ips


async def _revoke_user_sessions(redis_client: RedisCacheManager, user_id: str) -> int:
    session_pattern = f"session:{user_id}:*"
    cursor = b"0"
    revoked_count = 0
    while cursor:
        cursor, keys = await redis_client.client.scan(
            cursor=cursor, match=session_pattern, count=100
        )
        if keys:
            await redis_client.client.delete(*keys)
            revoked_count += len(keys)
    return revoked_count


@router.post("/login", response_model=TokenResponse)
async def login_access_token(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: RedisCacheManager = Depends(get_redis),
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_agent: Optional[str] = Header(None),
) -> Any:
    query = select(User).where(
        User.email == form_data.username, User.is_deleted == False
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    client_ip = request.client.host if request.client else "127.0.0.1"
    resolved_user_agent = user_agent or "unknown"

    if not user:
        await asyncio.sleep(0.5)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    if user.is_locked_out():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked",
        )

    if not verify_salted_password(form_data.password, user.salt, user.hashed_password):
        user.record_login_failure(
            settings.MAX_LOGIN_ATTEMPTS, settings.LOCKOUT_DURATION_MINUTES
        )
        failed_login = LoginHistory(
            user_id=user.id,
            ip_address=client_ip,
            user_agent=resolved_user_agent,
            status="FAILED",
            failure_reason="Invalid password",
        )
        db.add(failed_login)
        db.add(user)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive"
        )

    is_anomalous_ip = await _verify_ip_anomaly(db, user.id, client_ip)
    if is_anomalous_ip and settings.REQUIRE_MFA:
        pass

    user.record_login_success()
    success_login = LoginHistory(
        user_id=user.id,
        ip_address=client_ip,
        user_agent=resolved_user_agent,
        status="SUCCESS",
    )
    db.add(success_login)
    db.add(user)
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    role_value = user.role.value if hasattr(user.role, "value") else user.role

    access_token = create_access_token(
        user.id, role_value, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(user.id)

    session_id = os.urandom(16).hex()
    session_key = f"session:{user.id}:{session_id}"
    session_data = {"ip": client_ip, "ua": resolved_user_agent, "created": time.time()}

    try:
        await redis.set(
            session_key,
            session_data,
            ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as e:
        logger.warning(f"Redis is unavailable locally. Skipping session cache: {e}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_context={
            "id": user.id,
            "email": user.email,
            "role": role_value,
            "requires_password_change": user.requires_password_change,
        },
    )


@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_user),
    redis: RedisCacheManager = Depends(get_redis),
) -> Any:
    revoked = await _revoke_user_sessions(redis, current_user.id)
    return {
        "status": "success",
        "message": f"Successfully logged out. {revoked} active sessions terminated.",
    }


@router.post("/password/change")
async def change_password(
    request: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: RedisCacheManager = Depends(get_redis),
) -> Any:
    if request.new_password != request.confirm_new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match"
        )

    if not verify_salted_password(
        request.current_password, current_user.salt, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password"
        )

    if verify_salted_password(
        request.new_password, current_user.salt, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    new_salt = generate_salt()
    current_user.salt = new_salt
    current_user.hashed_password = hash_password_with_salt(
        request.new_password, new_salt
    )
    current_user.requires_password_change = False

    db.add(current_user)
    await db.commit()

    await _revoke_user_sessions(redis, current_user.id)

    return {
        "status": "success",
        "message": "Password updated successfully. All other sessions have been revoked.",
    }


@router.get("/sessions", response_model=List[ActiveSessionResponse])
async def list_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis: RedisCacheManager = Depends(get_redis),
) -> Any:
    session_pattern = f"session:{current_user.id}:*"
    cursor = b"0"
    sessions = []
    current_ip = request.client.host if request.client else "unknown"

    while cursor:
        cursor, keys = await redis.client.scan(
            cursor=cursor, match=session_pattern, count=100
        )
        for key in keys:
            data = await redis.get(key.decode("utf-8").replace(redis.prefix, ""))
            if data:
                session_id = key.decode("utf-8").split(":")[-1]
                sessions.append(
                    ActiveSessionResponse(
                        session_id=session_id,
                        ip_address=data.get("ip", "unknown"),
                        user_agent=data.get("ua", "unknown"),
                        created_at=datetime.fromtimestamp(
                            data.get("created", 0)
                        ).isoformat(),
                        last_active=datetime.fromtimestamp(
                            data.get("created", 0)
                        ).isoformat(),
                        is_current=data.get("ip") == current_ip,
                    )
                )
    return sessions


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    query = select(APIKey).where(
        APIKey.user_id == current_user.id, APIKey.status == APIKeyStatus.ACTIVE
    )
    result = await db.execute(query)
    active_keys = result.scalars().all()

    if len(active_keys) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of active API keys reached (5)",
        )

    from src.core.security import generate_api_key

    raw_key, prefix, hashed_key = generate_api_key()

    expiration_date = None
    if request.expiration_days:
        expiration_date = datetime.utcnow() + timedelta(days=request.expiration_days)

    new_key = APIKey(
        user_id=current_user.id,
        name=request.name,
        key_prefix=prefix,
        hashed_key=hashed_key,
        allowed_ips=request.allowed_ips,
        expires_at=expiration_date,
    )

    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    response_data = APIKeyResponse(
        id=new_key.id,
        name=new_key.name,
        prefix=new_key.key_prefix,
        raw_key=f"{prefix}.{raw_key}",
        status=new_key.status.value,
        expires_at=new_key.expires_at,
        created_at=new_key.created_at,
    )
    return response_data


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    query = select(APIKey).where(
        and_(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found"
        )

    api_key.revoke()
    db.add(api_key)
    await db.commit()

    return {"status": "success", "message": "API key successfully revoked"}
