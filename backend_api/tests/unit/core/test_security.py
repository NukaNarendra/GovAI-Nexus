import pytest
import time
from datetime import timedelta
from jose import jwt, JWTError

from src.core.security import (
    verify_password,
    get_password_hash,
    generate_salt,
    hash_password_with_salt,
    verify_salted_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_api_key,
)
from src.core.config import settings


def test_get_password_hash() -> None:
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert len(hashed) > 0
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_verify_password_success() -> None:
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    result = verify_password(password, hashed)
    assert result is True


def test_verify_password_failure() -> None:
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    result = verify_password("WrongPassword!", hashed)
    assert result is False


def test_generate_salt() -> None:
    salt1 = generate_salt()
    salt2 = generate_salt()
    assert len(salt1) == 64
    assert len(salt2) == 64
    assert salt1 != salt2


def test_hash_password_with_salt() -> None:
    password = "EnterprisePassword999"
    salt = generate_salt()
    hashed1 = hash_password_with_salt(password, salt)
    hashed2 = hash_password_with_salt(password, salt)
    assert hashed1 == hashed2
    assert len(hashed1) == 64

    different_salt = generate_salt()
    hashed3 = hash_password_with_salt(password, different_salt)
    assert hashed1 != hashed3


def test_verify_salted_password_success() -> None:
    password = "EnterprisePassword999"
    salt = generate_salt()
    hashed = hash_password_with_salt(password, salt)

    result = verify_salted_password(password, salt, hashed)
    assert result is True


def test_verify_salted_password_wrong_password() -> None:
    password = "EnterprisePassword999"
    salt = generate_salt()
    hashed = hash_password_with_salt(password, salt)

    result = verify_salted_password("WrongPassword999", salt, hashed)
    assert result is False


def test_verify_salted_password_wrong_salt() -> None:
    password = "EnterprisePassword999"
    salt = generate_salt()
    wrong_salt = generate_salt()
    hashed = hash_password_with_salt(password, salt)

    result = verify_salted_password(password, wrong_salt, hashed)
    assert result is False


def test_verify_salted_password_empty_inputs() -> None:
    assert verify_salted_password("pass", "", "hash") is False
    assert verify_salted_password("pass", "salt", "") is False


def test_create_access_token_default_expiry() -> None:
    subject = "user_123"
    role = "SYSTEM_ADMIN"
    token = create_access_token(subject=subject, role=role)

    assert isinstance(token, str)
    assert len(token) > 0

    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == subject
    assert decoded["role"] == role
    assert decoded["type"] == "access"
    assert "exp" in decoded


def test_create_access_token_custom_expiry() -> None:
    subject = "user_123"
    role = "READ_ONLY"
    delta = timedelta(minutes=5)

    token = create_access_token(subject=subject, role=role, expires_delta=delta)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    current_time = time.time()
    exp_time = decoded["exp"]
    diff = exp_time - current_time

    assert 290 < diff < 310


def test_create_refresh_token() -> None:
    subject = "user_456"
    token = create_refresh_token(subject=subject)

    assert isinstance(token, str)

    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == subject
    assert decoded["type"] == "refresh"
    assert "role" not in decoded


def test_decode_token_valid() -> None:
    subject = "user_789"
    token = create_access_token(subject=subject, role="AUDITOR")

    decoded = decode_token(token)
    assert decoded["sub"] == subject
    assert decoded["role"] == "AUDITOR"


def test_decode_token_invalid_signature() -> None:
    subject = "user_789"
    token = create_access_token(subject=subject, role="AUDITOR")

    tampered_token = token[:-5] + "aaaaa"

    with pytest.raises(ValueError) as exc:
        decode_token(tampered_token)
    assert "Invalid or expired token" in str(exc.value)


def test_decode_token_expired() -> None:
    subject = "user_789"
    delta = timedelta(seconds=-10)
    token = create_access_token(subject=subject, role="AUDITOR", expires_delta=delta)

    with pytest.raises(ValueError) as exc:
        decode_token(token)
    assert "Invalid or expired token" in str(exc.value)


def test_generate_api_key() -> None:
    raw_key, prefix, hashed_key = generate_api_key()

    assert len(raw_key) == 64
    assert len(prefix) == 8
    assert raw_key.startswith(prefix)
    assert len(hashed_key) == 64
    assert hashed_key != raw_key


def test_verify_api_key_success() -> None:
    raw_key, prefix, hashed_key = generate_api_key()
    result = verify_api_key(raw_key, hashed_key)
    assert result is True


def test_verify_api_key_failure() -> None:
    raw_key, prefix, hashed_key = generate_api_key()
    different_raw, _, _ = generate_api_key()

    result = verify_api_key(different_raw, hashed_key)
    assert result is False


def test_verify_api_key_tampered_hash() -> None:
    raw_key, prefix, hashed_key = generate_api_key()
    tampered_hash = hashed_key[:-1] + ("a" if hashed_key[-1] != "a" else "b")

    result = verify_api_key(raw_key, tampered_hash)
    assert result is False
