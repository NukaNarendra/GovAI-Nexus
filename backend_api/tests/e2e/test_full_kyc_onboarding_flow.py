import uuid
import pytest
from httpx import AsyncClient
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status

from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    RiskCategory,
)
from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
)
from src.infrastructure.database.models.user import User


@pytest.mark.asyncio
async def test_end_to_end_kyc_onboarding_requires_hitl_then_approved(
    async_client: AsyncClient,
    db_session: AsyncSession,
    compliance_officer_token: str,
    compliance_officer_user: User,
) -> None:
    entity_id = f"ENT_TEST_{uuid.uuid4().hex[:8].upper()}"
    onboarding_payload: Dict[str, Any] = {
        "entity_payload": {
            "entity_id": entity_id,
            "entity_name": "Nexus Global Trading LLC",
            "registration_number": "REG-1029384756",
            "incorporation_date": "2023-01-15",
            "country_of_incorporation": "CYM",
            "industry_code": "5094",
            "beneficial_owners": ["Alexander Sterling", "Victoria Chen"],
            "registered_address": {
                "street": "100 Offshore Parkway",
                "city": "George Town",
                "country": "CYM",
                "postal_code": "KY1-1102",
            },
        },
        "historical_data": [],
    }

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.post(
        "/api/v1/gateway/kyc/onboard", json=onboarding_payload, headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert "orchestration_id" in response_data
    assert response_data["status"] == "PENDING_HITL"
    assert response_data["requires_human_review"] is True
    assert response_data["governance_verdict"]["verdict"] == "ROUTED_TO_HITL"

    orchestration_id = response_data["orchestration_id"]

    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == entity_id)
    hitl_result = await db_session.execute(query_hitl)
    hitl_task = hitl_result.scalar_one_or_none()

    assert hitl_task is not None
    assert hitl_task.task_status == HITLTaskStatus.PENDING_REVIEW
    assert hitl_task.risk_category == RiskCategory.KYC_ANOMALY

    task_id = hitl_task.id

    claim_response = await async_client.post(
        f"/api/v1/hitl/tasks/{task_id}/claim", headers=headers
    )

    assert claim_response.status_code == status.HTTP_200_OK
    claim_data = claim_response.json()
    assert claim_data["status"] == HITLTaskStatus.UNDER_REVIEW.value
    assert claim_data["reviewer_id"] == compliance_officer_user.id

    resolution_payload = {
        "resolution_status": "APPROVED",
        "officer_notes": "Reviewed complex Cayman ownership structure. Verified UBOs via secondary ID checks. Risk accepted within tolerance parameters.",
        "action_taken": "MANUAL_VERIFICATION_AND_APPROVAL",
        "generate_ai_feedback": True,
    }

    resolve_response = await async_client.post(
        f"/api/v1/hitl/tasks/{task_id}/resolve",
        json=resolution_payload,
        headers=headers,
    )

    assert resolve_response.status_code == status.HTTP_200_OK
    resolve_data = resolve_response.json()
    assert resolve_data["status"] == "RESOLVED"
    assert resolve_data["resolution"] == "APPROVED"
    assert resolve_data["feedback_loop_generated"] is True

    await db_session.refresh(hitl_task)
    assert hitl_task.task_status == HITLTaskStatus.APPROVED
    assert hitl_task.resolution_action == "MANUAL_VERIFICATION_AND_APPROVAL"
    assert hitl_task.resolved_at is not None

    query_audit = (
        select(AuditLog)
        .where(AuditLog.resource_id == entity_id)
        .order_by(AuditLog.timestamp.asc())
    )
    audit_result = await db_session.execute(query_audit)
    audit_logs = list(audit_result.scalars().all())

    assert len(audit_logs) >= 2

    ai_execution_log = next(
        (
            log
            for log in audit_logs
            if log.event_type == AuditEventType.AI_DECISION_EXECUTED
        ),
        None,
    )
    assert ai_execution_log is not None
    assert ai_execution_log.severity == ActionSeverity.MEDIUM
    assert "PENDING_HITL" in ai_execution_log.action_details
    assert ai_execution_log.cryptographic_hash is not None

    hitl_resolution_log = next(
        (log for log in audit_logs if log.event_type == AuditEventType.HITL_APPROVAL),
        None,
    )
    assert hitl_resolution_log is not None
    assert hitl_resolution_log.severity == ActionSeverity.HIGH
    assert hitl_resolution_log.actor_id == compliance_officer_user.id
    assert hitl_resolution_log.new_state is not None
    assert hitl_resolution_log.new_state["hitl_task_id"] == task_id
    assert hitl_resolution_log.new_state["new_status"] == "APPROVED"

    assert hitl_resolution_log.verify_integrity() is True


@pytest.mark.asyncio
async def test_kyc_onboarding_auto_rejection_for_sanctioned_entity(
    async_client: AsyncClient, db_session: AsyncSession, compliance_officer_token: str
) -> None:
    entity_id = f"ENT_TEST_{uuid.uuid4().hex[:8].upper()}"
    onboarding_payload: Dict[str, Any] = {
        "entity_payload": {
            "entity_id": entity_id,
            "entity_name": "GLOBAL SHELL CORP",
            "registration_number": "REG-000000000",
            "incorporation_date": "2023-11-01",
            "country_of_incorporation": "IRN",
            "industry_code": "6021",
            "beneficial_owners": ["Hidden Owner A"],
            "registered_address": {
                "street": "PO Box 123",
                "city": "Tehran",
                "country": "IRN",
                "postal_code": "12345",
            },
        },
        "historical_data": [],
    }

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.post(
        "/api/v1/gateway/kyc/onboard", json=onboarding_payload, headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert response_data["status"] == "REJECTED"
    assert response_data["requires_human_review"] is False
    assert response_data["governance_verdict"]["verdict"] == "REJECTED_AUTO"
    assert response_data["governance_verdict"]["requires_hard_block"] is True

    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == entity_id)
    hitl_result = await db_session.execute(query_hitl)
    hitl_task = hitl_result.scalar_one_or_none()
    assert hitl_task is None

    query_audit = select(AuditLog).where(AuditLog.resource_id == entity_id)
    audit_result = await db_session.execute(query_audit)
    audit_log = audit_result.scalar_one_or_none()

    assert audit_log is not None
    assert audit_log.event_type == AuditEventType.AI_DECISION_EXECUTED
    assert audit_log.severity == ActionSeverity.HIGH
    assert audit_log.verify_integrity() is True
