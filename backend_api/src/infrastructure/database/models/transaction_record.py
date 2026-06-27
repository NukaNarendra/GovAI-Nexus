import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
from sqlalchemy import String, DateTime, JSON, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from src.infrastructure.database.session import Base


class TransactionState(str, Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    PENDING_COMPLIANCE = "PENDING_COMPLIANCE"
    CLEARED = "CLEARED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"
    BLOCKED_SANCTIONS = "BLOCKED_SANCTIONS"
    BLOCKED_FRAUD = "BLOCKED_FRAUD"


class TransactionType(str, Enum):
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    DOMESTIC_WIRE = "DOMESTIC_WIRE"
    INTERNATIONAL_WIRE = "INTERNATIONAL_WIRE"
    ACH_DEBIT = "ACH_DEBIT"
    ACH_CREDIT = "ACH_CREDIT"
    FEE_COLLECTION = "FEE_COLLECTION"


class TransactionRecord(Base):
    __tablename__ = "transaction_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    reference_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    core_banking_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
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
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[TransactionState] = mapped_column(
        String(50), nullable=False, default=TransactionState.INITIATED, index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        String(50), nullable=False
    )

    source_entity_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    source_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_country: Mapped[str] = mapped_column(String(3), nullable=False)

    destination_entity_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    destination_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_country: Mapped[str] = mapped_column(String(3), nullable=False)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    base_currency_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    ai_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ai_confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    compliance_passed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    requires_hitl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sanctions_screened: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    aml_screened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    velocity_checked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    compliance_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    routing_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    audit_log_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True
    )
    hitl_queue_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("hitl_review_queue.id", ondelete="SET NULL"),
        nullable=True,
    )

    audit_log = relationship("AuditLog", foreign_keys=[audit_log_id], lazy="selectin")
    hitl_review = relationship(
        "HITLQueue", foreign_keys=[hitl_queue_id], lazy="selectin"
    )

    def transition_state(self, new_state: TransactionState, reason: str = None) -> None:
        valid_transitions = {
            TransactionState.INITIATED: [
                TransactionState.PROCESSING,
                TransactionState.FAILED,
            ],
            TransactionState.PROCESSING: [
                TransactionState.PENDING_COMPLIANCE,
                TransactionState.CLEARED,
                TransactionState.FAILED,
            ],
            TransactionState.PENDING_COMPLIANCE: [
                TransactionState.CLEARED,
                TransactionState.BLOCKED_SANCTIONS,
                TransactionState.BLOCKED_FRAUD,
                TransactionState.FAILED,
            ],
            TransactionState.CLEARED: [
                TransactionState.EXECUTED,
                TransactionState.FAILED,
            ],
            TransactionState.EXECUTED: [TransactionState.REVERSED],
            TransactionState.FAILED: [],
            TransactionState.REVERSED: [],
            TransactionState.BLOCKED_SANCTIONS: [],
            TransactionState.BLOCKED_FRAUD: [],
        }

        if new_state not in valid_transitions.get(self.status, []):
            raise ValueError(
                f"Invalid state transition from {self.status} to {new_state}"
            )

        self.status = new_state
        if reason:
            self.failure_reason = reason

        if new_state == TransactionState.EXECUTED:
            self.executed_at = datetime.utcnow()

    def mark_compliance_cleared(
        self, risk_score: float, metadata: Dict[str, Any]
    ) -> None:
        if (
            self.status != TransactionState.PROCESSING
            and self.status != TransactionState.PENDING_COMPLIANCE
        ):
            raise ValueError(
                "Transaction must be in PROCESSING or PENDING_COMPLIANCE to be cleared"
            )

        self.compliance_passed = True
        self.sanctions_screened = True
        self.aml_screened = True
        self.velocity_checked = True
        self.ai_risk_score = risk_score
        self.compliance_metadata.update(metadata)
        self.transition_state(TransactionState.CLEARED)

    def mark_compliance_blocked(
        self,
        block_type: TransactionState,
        risk_score: float,
        reason: str,
        metadata: Dict[str, Any],
    ) -> None:
        if block_type not in [
            TransactionState.BLOCKED_SANCTIONS,
            TransactionState.BLOCKED_FRAUD,
        ]:
            raise ValueError("Invalid block type")

        self.compliance_passed = False
        self.ai_risk_score = risk_score
        self.compliance_metadata.update(metadata)
        self.transition_state(block_type, reason)

    def is_cross_border(self) -> bool:
        return self.source_country.upper() != self.destination_country.upper()

    def get_risk_profile(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.id,
            "risk_score": self.ai_risk_score,
            "confidence_score": self.ai_confidence_score,
            "cross_border": self.is_cross_border(),
            "high_risk_corridor": self.is_cross_border()
            and (
                self.source_country in ["IRN", "PRK", "SYR"]
                or self.destination_country in ["IRN", "PRK", "SYR"]
            ),
            "amount_usd_equivalent": self.base_currency_amount
            if self.base_currency_amount
            else self.amount,
        }
