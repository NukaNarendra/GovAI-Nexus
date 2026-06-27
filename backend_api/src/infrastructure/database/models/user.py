import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum
import hashlib
import os
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from src.infrastructure.database.session import Base


class UserRole(str, Enum):
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    RISK_ANALYST = "RISK_ANALYST"
    AUDITOR = "AUDITOR"
    READ_ONLY = "READ_ONLY"


class APIKeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None


user_department_association = Table(
    "user_department_link",
    Base.metadata,
    Column(
        "user_id",
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "department_id",
        String(36),
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    cost_center_code: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)

    users: Mapped[List["User"]] = relationship(
        "User", secondary=user_department_association, back_populates="departments"
    )


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(50), nullable=False, default=UserRole.READ_ONLY
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_password_change: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    account_locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    login_history: Mapped[List["LoginHistory"]] = relationship(
        "LoginHistory", back_populates="user", cascade="all, delete-orphan"
    )
    departments: Mapped[List["Department"]] = relationship(
        "Department", secondary=user_department_association, back_populates="users"
    )

    def set_password(self, raw_password: str) -> None:
        self.salt = os.urandom(32).hex()
        encoded_password = raw_password.encode("utf-8")
        encoded_salt = self.salt.encode("utf-8")
        self.hashed_password = hashlib.pbkdf2_hmac(
            "sha256", encoded_password, encoded_salt, 100000
        ).hex()

    def verify_password(self, raw_password: str) -> bool:
        if not self.salt or not self.hashed_password:
            return False
        encoded_password = raw_password.encode("utf-8")
        encoded_salt = self.salt.encode("utf-8")
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256", encoded_password, encoded_salt, 100000
        ).hex()
        return hmac.compare_digest(self.hashed_password, computed_hash)

    def record_login_success(self) -> None:
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.last_login_at = datetime.utcnow()

    def record_login_failure(
        self, max_attempts: int = 5, lockout_minutes: int = 15
    ) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta

            self.account_locked_until = datetime.utcnow() + timedelta(
                minutes=lockout_minutes
            )

    def is_locked_out(self) -> bool:
        if self.account_locked_until is None:
            return False
        if datetime.utcnow() > self.account_locked_until:
            self.failed_login_attempts = 0
            self.account_locked_until = None
            return False
        return True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    hashed_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[APIKeyStatus] = mapped_column(
        String(20), nullable=False, default=APIKeyStatus.ACTIVE
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    allowed_ips: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    def is_valid(self) -> bool:
        if self.status != APIKeyStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            self.status = APIKeyStatus.EXPIRED
            return False
        return True

    def revoke(self) -> None:
        self.status = APIKeyStatus.REVOKED


class LoginHistory(Base):
    __tablename__ = "login_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    login_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="login_history")
