import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
from sqlalchemy import String, DateTime, JSON, Boolean, Float, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from src.infrastructure.database.session import Base


class HITLTaskStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class RiskCategory(str, Enum):
    KYC_ANOMALY = "KYC_ANOMALY"
    AML_FLAG = "AML_FLAG"
    SANCTIONS_MATCH = "SANCTIONS_MATCH"
    HIGH_VALUE_TRANSFER = "HIGH_VALUE_TRANSFER"
    UNUSUAL_VELOCITY = "UNUSUAL_VELOCITY"
    AI_CONFIDENCE_LOW = "AI_CONFIDENCE_LOW"
    SYSTEM_ANOMALY = "SYSTEM_ANOMALY"


class PriorityLevel(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class HITLQueue(Base):
    __tablename__ = "hitl_review_queue"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    task_status: Mapped[HITLTaskStatus] = mapped_column(
        String(30), nullable=False, default=HITLTaskStatus.PENDING_REVIEW, index=True
    )
    risk_category: Mapped[RiskCategory] = mapped_column(
        String(50), nullable=False, index=True
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        Integer, nullable=False, default=PriorityLevel.MEDIUM, index=True
    )

    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ai_confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)

    transaction_context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    compliance_flags: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    reviewer_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    deadline_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_sla_breached: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    audit_log_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True
    )

    reviewer = relationship("User", foreign_keys=[reviewer_id], lazy="selectin")
    audit_log = relationship("AuditLog", foreign_keys=[audit_log_id], lazy="selectin")

    def claim_task(self, user_id: str) -> None:
        if (
            self.task_status != HITLTaskStatus.PENDING_REVIEW
            and self.task_status != HITLTaskStatus.ESCALATED
        ):
            raise ValueError(
                f"Task {self.id} cannot be claimed. Current status: {self.task_status}"
            )
        self.task_status = HITLTaskStatus.UNDER_REVIEW
        self.reviewer_id = user_id
        self.claimed_at = datetime.utcnow()

    def unclaim_task(self, user_id: str) -> None:
        if self.reviewer_id != user_id:
            raise ValueError(
                f"User {user_id} cannot unclaim task {self.id} claimed by {self.reviewer_id}"
            )
        self.task_status = HITLTaskStatus.PENDING_REVIEW
        self.reviewer_id = None
        self.claimed_at = None

    def resolve_task(
        self, user_id: str, status: HITLTaskStatus, notes: str, action: str
    ) -> None:
        if self.reviewer_id != user_id:
            raise ValueError(
                f"User {user_id} is not authorized to resolve task {self.id}"
            )
        if status not in [HITLTaskStatus.APPROVED, HITLTaskStatus.REJECTED]:
            raise ValueError("Resolution status must be APPROVED or REJECTED")

        self.task_status = status
        self.resolution_notes = notes
        self.resolution_action = action
        self.resolved_at = datetime.utcnow()
        self.check_sla_breach()

    def escalate_task(self, user_id: str, escalation_reason: str) -> None:
        if self.reviewer_id != user_id:
            raise ValueError("Only the assigned reviewer can escalate the task")

        self.task_status = HITLTaskStatus.ESCALATED
        self.resolution_notes = f"ESCALATED: {escalation_reason}"
        self.priority = PriorityLevel.CRITICAL
        self.reviewer_id = None
        self.claimed_at = None

    def check_sla_breach(self) -> bool:
        if not self.deadline_at:
            return False

        check_time = self.resolved_at if self.resolved_at else datetime.utcnow()
        if check_time > self.deadline_at:
            self.is_sla_breached = True
            return True
        return False

    @property
    def processing_time_seconds(self) -> Optional[float]:
        if not self.claimed_at or not self.resolved_at:
            return None
        return (self.resolved_at - self.claimed_at).total_seconds()

    @property
    def time_in_queue_seconds(self) -> float:
        end_time = self.claimed_at if self.claimed_at else datetime.utcnow()
        return (end_time - self.created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.task_status.value
            if hasattr(self.task_status, "value")
            else self.task_status,
            "risk_category": self.risk_category.value
            if hasattr(self.risk_category, "value")
            else self.risk_category,
            "priority": self.priority.value
            if hasattr(self.priority, "value")
            else self.priority,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "ai_confidence_score": self.ai_confidence_score,
            "created_at": self.created_at.isoformat(),
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "is_sla_breached": self.is_sla_breached,
            "reviewer_id": self.reviewer_id,
            "time_in_queue": self.time_in_queue_seconds,
        }
