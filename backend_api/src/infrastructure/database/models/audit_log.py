import uuid
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
from sqlalchemy import String, DateTime, Integer, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from src.infrastructure.database.session import Base


class AuditEventType(str, Enum):
    AI_DECISION_EXECUTED = "AI_DECISION_EXECUTED"
    AI_DECISION_REJECTED = "AI_DECISION_REJECTED"
    HITL_OVERRIDE = "HITL_OVERRIDE"
    HITL_APPROVAL = "HITL_APPROVAL"
    COMPLIANCE_RULE_TRIGGERED = "COMPLIANCE_RULE_TRIGGERED"
    RISK_THRESHOLD_EXCEEDED = "RISK_THRESHOLD_EXCEEDED"
    DATA_INTEGRATION_SYNC = "DATA_INTEGRATION_SYNC"
    SYSTEM_CONFIGURATION_CHANGED = "SYSTEM_CONFIGURATION_CHANGED"
    USER_AUTHENTICATION = "USER_AUTHENTICATION"
    API_KEY_GENERATED = "API_KEY_GENERATED"


class ActorType(str, Enum):
    AI_AGENT = "AI_AGENT"
    HUMAN_USER = "HUMAN_USER"
    SYSTEM_PROCESS = "SYSTEM_PROCESS"
    EXTERNAL_API = "EXTERNAL_API"


class ActionSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        String(50), nullable=False, index=True
    )
    severity: Mapped[ActionSeverity] = mapped_column(
        String(20), nullable=False, default=ActionSeverity.INFO
    )

    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_type: Mapped[ActorType] = mapped_column(String(30), nullable=False)
    actor_ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    action_details: Mapped[str] = mapped_column(Text, nullable=False)

    old_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    cryptographic_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_tampered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    compliance_frameworks: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    ai_model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def calculate_hash(self, prev_hash: str = None) -> str:
        payload = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value
            if hasattr(self.event_type, "value")
            else self.event_type,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type.value
            if hasattr(self.actor_type, "value")
            else self.actor_type,
            "resource_id": self.resource_id,
            "action_details": self.action_details,
            "old_state": json.dumps(self.old_state, sort_keys=True)
            if self.old_state
            else None,
            "new_state": json.dumps(self.new_state, sort_keys=True)
            if self.new_state
            else None,
            "previous_hash": prev_hash or self.previous_hash,
        }
        canonical_string = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_string).hexdigest()

    def seal_log(self, prev_hash: str = None) -> None:
        if prev_hash:
            self.previous_hash = prev_hash
        self.cryptographic_hash = self.calculate_hash(self.previous_hash)

    def verify_integrity(self) -> bool:
        if not self.cryptographic_hash:
            return False
        expected_hash = self.calculate_hash(self.previous_hash)
        is_valid = hmac.compare_digest(self.cryptographic_hash, expected_hash)
        if not is_valid:
            self.is_tampered = True
        return is_valid

    @classmethod
    def create_ai_execution_log(
        cls,
        agent_id: str,
        action: str,
        target_resource: str,
        payload: Dict[str, Any],
        model_version: str,
        tokens_used: Dict[str, int],
    ) -> "AuditLog":
        log = cls(
            event_type=AuditEventType.AI_DECISION_EXECUTED,
            severity=ActionSeverity.HIGH,
            actor_id=agent_id,
            actor_type=ActorType.AI_AGENT,
            resource_id=target_resource,
            resource_type="FINANCIAL_TRANSACTION",
            action_details=action,
            new_state=payload,
            ai_model_version=model_version,
            ai_prompt_tokens=tokens_used.get("prompt"),
            ai_completion_tokens=tokens_used.get("completion"),
            correlation_id=str(uuid.uuid4()),
        )
        return log

    @classmethod
    def create_hitl_override_log(
        cls,
        officer_id: str,
        original_agent_id: str,
        resource_id: str,
        override_reason: str,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> "AuditLog":
        log = cls(
            event_type=AuditEventType.HITL_OVERRIDE,
            severity=ActionSeverity.CRITICAL,
            actor_id=officer_id,
            actor_type=ActorType.HUMAN_USER,
            resource_id=resource_id,
            resource_type="GOVERNANCE_QUEUE",
            action_details=f"Human override of AI agent {original_agent_id}. Reason: {override_reason}",
            old_state=old_data,
            new_state=new_data,
            correlation_id=str(uuid.uuid4()),
        )
        return log
