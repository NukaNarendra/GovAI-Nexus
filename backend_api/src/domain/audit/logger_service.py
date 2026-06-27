import re
import uuid
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Union
from sqlalchemy.ext.asyncio import AsyncSession
from contextvars import ContextVar

from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
    ActorType,
)
from src.infrastructure.database.repository.audit_repo import AuditLogRepository

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
actor_id_ctx: ContextVar[str] = ContextVar("actor_id", default="SYSTEM")
actor_type_ctx: ContextVar[ActorType] = ContextVar(
    "actor_type", default=ActorType.SYSTEM_PROCESS
)


class AuditLoggerError(Exception):
    pass


class PIIScrubber:
    def __init__(self):
        self.sensitive_keys: Set[str] = {
            "password",
            "ssn",
            "social_security",
            "tax_id",
            "credit_card",
            "card_number",
            "cvv",
            "dob",
            "date_of_birth",
            "passcode",
            "secret",
            "private_key",
            "beneficial_owner_id_number",
            "passport_number",
        }
        self.email_pattern = re.compile(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        )
        self.ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        self.card_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

    def scrub_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        scrubbed = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_keys):
                scrubbed[key] = "[REDACTED]"
            elif isinstance(value, dict):
                scrubbed[key] = self.scrub_dict(value)
            elif isinstance(value, list):
                scrubbed[key] = self.scrub_list(value)
            elif isinstance(value, str):
                scrubbed[key] = self.scrub_string(value)
            else:
                scrubbed[key] = value
        return scrubbed

    def scrub_list(self, items: List[Any]) -> List[Any]:
        scrubbed = []
        for item in items:
            if isinstance(item, dict):
                scrubbed.append(self.scrub_dict(item))
            elif isinstance(item, list):
                scrubbed.append(self.scrub_list(item))
            elif isinstance(item, str):
                scrubbed.append(self.scrub_string(item))
            else:
                scrubbed.append(item)
        return scrubbed

    def scrub_string(self, text: str) -> str:
        text = self.email_pattern.sub("[EMAIL_REDACTED]", text)
        text = self.ssn_pattern.sub("[SSN_REDACTED]", text)
        text = self.card_pattern.sub("[CARD_REDACTED]", text)
        return text


class AuditLoggerService:
    def __init__(self, repository: AuditLogRepository, worm_storage: Any):
        self.repository = repository
        self.worm_storage = worm_storage
        self.pii_scrubber = PIIScrubber()

    def set_context(
        self, correlation_id: str, actor_id: str, actor_type: ActorType
    ) -> None:
        correlation_id_ctx.set(correlation_id)
        actor_id_ctx.set(actor_id)
        actor_type_ctx.set(actor_type)

    def get_correlation_id(self) -> str:
        cid = correlation_id_ctx.get()
        if not cid:
            cid = str(uuid.uuid4())
            correlation_id_ctx.set(cid)
        return cid

    async def _dispatch_log(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        severity: ActionSeverity,
        resource_id: str,
        resource_type: str,
        action_details: str,
        old_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        ai_metrics: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        safe_old_state = self.pii_scrubber.scrub_dict(old_state) if old_state else None
        safe_new_state = self.pii_scrubber.scrub_dict(new_state) if new_state else None

        log_entry = AuditLog(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id_ctx.get(),
            actor_type=actor_type_ctx.get(),
            resource_id=resource_id,
            resource_type=resource_type,
            action_details=action_details,
            old_state=safe_old_state,
            new_state=safe_new_state,
            correlation_id=self.get_correlation_id(),
        )

        if ai_metrics:
            log_entry.ai_model_version = ai_metrics.get("model_used")
            log_entry.ai_prompt_tokens = ai_metrics.get("prompt_tokens")
            log_entry.ai_completion_tokens = ai_metrics.get("completion_tokens")

        return await self.worm_storage.append_immutable_record(db, log_entry)

    async def log_ai_execution(
        self,
        db: AsyncSession,
        agent_id: str,
        resource_id: str,
        resource_type: str,
        execution_directive: str,
        payload: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        governance_verdict: str,
    ) -> AuditLog:
        self.set_context(self.get_correlation_id(), agent_id, ActorType.AI_AGENT)

        severity = ActionSeverity.INFO
        if execution_directive in ["BLOCK_TRANSACTION", "REJECT"]:
            severity = ActionSeverity.HIGH
        elif execution_directive in ["HOLD_FOR_REVIEW", "PENDING_HITL"]:
            severity = ActionSeverity.MEDIUM

        action_details = f"AI Execution: {execution_directive}. Governance Verdict: {governance_verdict}."

        return await self._dispatch_log(
            db=db,
            event_type=AuditEventType.AI_DECISION_EXECUTED,
            severity=severity,
            resource_id=resource_id,
            resource_type=resource_type,
            action_details=action_details,
            new_state=payload,
            ai_metrics={
                "model_used": ai_analysis.get("model_used", "UNKNOWN"),
                "prompt_tokens": ai_analysis.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": ai_analysis.get("usage", {}).get(
                    "completion_tokens", 0
                ),
            },
        )

    async def log_hitl_resolution(
        self,
        db: AsyncSession,
        officer_id: str,
        task_id: str,
        resource_id: str,
        resolution_status: str,
        officer_notes: str,
        ai_learning_feedback: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        self.set_context(self.get_correlation_id(), officer_id, ActorType.HUMAN_USER)

        event_type = AuditEventType.HITL_APPROVAL
        if resolution_status == "REJECTED":
            event_type = AuditEventType.HITL_OVERRIDE

        action_details = (
            f"HITL Resolution: {resolution_status}. Officer Notes: {officer_notes}"
        )

        return await self._dispatch_log(
            db=db,
            event_type=event_type,
            severity=ActionSeverity.HIGH,
            resource_id=resource_id,
            resource_type="FINANCIAL_RESOURCE",
            action_details=action_details,
            old_state={"hitl_task_id": task_id, "previous_status": "PENDING_REVIEW"},
            new_state={
                "hitl_task_id": task_id,
                "new_status": resolution_status,
                "ai_feedback_loop": ai_learning_feedback,
            },
        )

    async def log_compliance_violation(
        self,
        db: AsyncSession,
        resource_id: str,
        resource_type: str,
        violation_codes: List[str],
        risk_score: float,
        system_notes: str,
    ) -> AuditLog:
        self.set_context(
            self.get_correlation_id(), "GOVERNANCE_ENGINE", ActorType.SYSTEM_PROCESS
        )

        severity = ActionSeverity.CRITICAL if risk_score > 85.0 else ActionSeverity.HIGH

        action_details = (
            f"Compliance Violation Block. Score: {risk_score}. Notes: {system_notes}"
        )

        return await self._dispatch_log(
            db=db,
            event_type=AuditEventType.COMPLIANCE_RULE_TRIGGERED,
            severity=severity,
            resource_id=resource_id,
            resource_type=resource_type,
            action_details=action_details,
            new_state={"violations": violation_codes, "calculated_risk": risk_score},
        )

    async def log_security_event(
        self,
        db: AsyncSession,
        user_id: str,
        event_type: AuditEventType,
        details: str,
        ip_address: str,
    ) -> AuditLog:
        self.set_context(self.get_correlation_id(), user_id, ActorType.HUMAN_USER)

        return await self._dispatch_log(
            db=db,
            event_type=event_type,
            severity=ActionSeverity.CRITICAL
            if event_type == AuditEventType.SYSTEM_CONFIGURATION_CHANGED
            else ActionSeverity.INFO,
            resource_id=user_id,
            resource_type="USER_ACCOUNT",
            action_details=details,
            new_state={"ip_address": self.pii_scrubber.scrub_string(ip_address)},
        )
