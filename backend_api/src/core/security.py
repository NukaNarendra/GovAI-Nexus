import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Any, Union, Optional, Dict
from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_salt() -> str:
    return os.urandom(32).hex()


def hash_password_with_salt(password: str, salt: str) -> str:
    encoded_password = password.encode("utf-8")
    encoded_salt = salt.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", encoded_password, encoded_salt, 100000).hex()


def verify_salted_password(
    plain_password: str, salt: str, hashed_password: str
) -> bool:
    if not salt or not hashed_password:
        return False
    computed_hash = hash_password_with_salt(plain_password, salt)
    return hmac.compare_digest(hashed_password, computed_hash)


def create_access_token(
    subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None
) -> str:
    from src.core.config import settings

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject), "role": role, "type": "access"}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any]) -> str:
    from src.core.config import settings

    expire = datetime.utcnow() + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    from src.core.config import settings

    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return decoded_token
    except JWTError:
        raise ValueError("Invalid or expired token")


def generate_api_key() -> tuple[str, str, str]:
    raw_key = os.urandom(32).hex()
    prefix = raw_key[:8]
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, prefix, hashed_key


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    computed_hash = hashlib.sha256(plain_key.encode("utf-8")).hexdigest()
    return hmac.compare_digest(computed_hash, hashed_key)
