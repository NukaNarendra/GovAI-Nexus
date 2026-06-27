import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import status
from datetime import datetime, timedelta

from src.infrastructure.database.models.user import User, UserRole, APIKey, LoginHistory
from src.core.security import verify_salted_password


@pytest.mark.asyncio
async def test_successful_login_returns_valid_tokens(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_user_password: str,
) -> None:
    login_data = {
        "username": test_user.email,
        "password": test_user_password,
        "grant_type": "password",
    }

    response = await async_client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Pytest-Integration-Client",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert response_data["token_type"] == "bearer"
    assert response_data["user_context"]["email"] == test_user.email
    assert response_data["user_context"]["role"] == test_user.role.value

    await db_session.refresh(test_user)
    assert test_user.failed_login_attempts == 0
    assert test_user.last_login_at is not None

    query = (
        select(LoginHistory)
        .where(LoginHistory.user_id == test_user.id)
        .order_by(LoginHistory.login_time.desc())
    )
    result = await db_session.execute(query)
    history = result.scalars().first()

    assert history is not None
    assert history.status == "SUCCESS"
    assert history.user_agent == "Pytest-Integration-Client"


@pytest.mark.asyncio
async def test_failed_login_triggers_account_lockout(
    async_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    login_data = {
        "username": test_user.email,
        "password": "wrong_password_123",
        "grant_type": "password",
    }

    for _ in range(5):
        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    await db_session.refresh(test_user)
    assert test_user.failed_login_attempts == 5
    assert test_user.account_locked_until is not None
    assert test_user.account_locked_until > datetime.utcnow()

    locked_response = await async_client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert locked_response.status_code == status.HTTP_403_FORBIDDEN
    assert "locked" in locked_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_inactive_user_cannot_login(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_user_password: str,
) -> None:
    test_user.is_active = False
    db_session.add(test_user)
    await db_session.commit()

    login_data = {
        "username": test_user.email,
        "password": test_user_password,
        "grant_type": "password",
    }

    response = await async_client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive" in response.json()["detail"].lower()

    test_user.is_active = True
    db_session.add(test_user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_current_user_profile(
    async_client: AsyncClient, normal_user_token: str, test_user: User
) -> None:
    response = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {normal_user_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert response_data["id"] == test_user.id
    assert response_data["email"] == test_user.email
    assert response_data["first_name"] == test_user.first_name
    assert response_data["last_name"] == test_user.last_name
    assert response_data["role"] == test_user.role.value


@pytest.mark.asyncio
async def test_password_change_revokes_sessions(
    async_client: AsyncClient,
    db_session: AsyncSession,
    normal_user_token: str,
    test_user: User,
    test_user_password: str,
) -> None:
    new_password = "NewComplexPassword123!"

    payload = {
        "current_password": test_user_password,
        "new_password": new_password,
        "confirm_new_password": new_password,
    }

    response = await async_client.post(
        "/api/v1/auth/password/change",
        json=payload,
        headers={"Authorization": f"Bearer {normal_user_token}"},
    )

    assert response.status_code == status.HTTP_200_OK

    await db_session.refresh(test_user)
    assert (
        verify_salted_password(new_password, test_user.salt, test_user.hashed_password)
        is True
    )
    assert (
        verify_salted_password(
            test_user_password, test_user.salt, test_user.hashed_password
        )
        is False
    )
    assert test_user.requires_password_change is False

    sessions_response = await async_client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {normal_user_token}"},
    )
    assert sessions_response.status_code == status.HTTP_200_OK
    assert len(sessions_response.json()) == 0


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_limits(
    async_client: AsyncClient,
    db_session: AsyncSession,
    normal_user_token: str,
    test_user: User,
) -> None:
    await db_session.execute(delete(APIKey).where(APIKey.user_id == test_user.id))
    await db_session.commit()

    headers = {"Authorization": f"Bearer {normal_user_token}"}

    key_ids = []
    for i in range(5):
        payload = {
            "name": f"Integration Key {i}",
            "expiration_days": 30,
            "allowed_ips": "192.168.1.1",
        }
        response = await async_client.post(
            "/api/v1/auth/api-keys", json=payload, headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["raw_key"] is not None
        assert data["prefix"] in data["raw_key"]
        key_ids.append(data["id"])

    payload_6 = {"name": "Too Many Keys", "expiration_days": 30}
    response_6 = await async_client.post(
        "/api/v1/auth/api-keys", json=payload_6, headers=headers
    )
    assert response_6.status_code == status.HTTP_400_BAD_REQUEST

    target_key_id = key_ids[0]
    revoke_response = await async_client.delete(
        f"/api/v1/auth/api-keys/{target_key_id}", headers=headers
    )
    assert revoke_response.status_code == status.HTTP_200_OK

    query = select(APIKey).where(APIKey.id == target_key_id)
    result = await db_session.execute(query)
    revoked_key = result.scalar_one_or_none()
    assert revoked_key is not None
    assert revoked_key.status.value == "REVOKED"

    response_7 = await async_client.post(
        "/api/v1/auth/api-keys", json=payload_6, headers=headers
    )
    assert response_7.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_logout_invalidates_current_session(
    async_client: AsyncClient, normal_user_token: str
) -> None:
    headers = {"Authorization": f"Bearer {normal_user_token}"}

    sessions_before = await async_client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions_before.status_code == status.HTTP_200_OK

    logout_response = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == status.HTTP_200_OK

    sessions_after = await async_client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions_after.status_code == status.HTTP_200_OK
    assert len(sessions_after.json()) == 0
