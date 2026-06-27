import pytest
import uuid
from typing import Dict, Any, List
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status

from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    RiskCategory,
    PriorityLevel,
)
from src.infrastructure.database.models.audit_log import AuditLog, AuditEventType
from src.infrastructure.database.models.user import User
from src.domain.ai_agents.orchestrator import AIAgentOrchestrator
from src.api.dependencies import get_llm_client
from src.main import app


class MockLLMForFeedback:
    async def generate_json_structured_output(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "parsed_data": {
                "ai_was_correct": False,
                "discrepancy_analysis": {
                    "root_cause_category": "MISSING_CONTEXT",
                    "human_insight_extracted": "Human verified offline paper trail not visible to AI.",
                    "prompt_adjustment_recommendation": "Instruct AI to request paper trailing before blocking.",
                },
                "confidence_calibration_adjustment": -0.05,
            },
            "model_used": "mock-llama",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }


def override_llm_client():
    return MockLLMForFeedback()


@pytest.fixture
async def seeded_hitl_tasks(db_session: AsyncSession) -> List[HITLQueue]:
    tasks = []
    for i in range(5):
        task = HITLQueue(
            id=f"TASK_{uuid.uuid4().hex[:8]}",
            task_status=HITLTaskStatus.PENDING_REVIEW,
            risk_category=RiskCategory.AML_FLAG
            if i % 2 == 0
            else RiskCategory.KYC_ANOMALY,
            priority=PriorityLevel.HIGH if i == 0 else PriorityLevel.MEDIUM,
            agent_id="AGENT_1",
            model_version="v1",
            ai_confidence_score=0.75,
            resource_id=f"RES_{i}",
            resource_type="WIRE_TRANSFER",
            transaction_context={"amount": i * 1000},
            compliance_flags={"mock": True},
            ai_reasoning=f"Reason {i}",
        )
        db_session.add(task)
        tasks.append(task)
    await db_session.commit()
    for task in tasks:
        await db_session.refresh(task)
    return tasks


@pytest.mark.asyncio
async def test_list_pending_tasks_pagination_and_filtering(
    async_client: AsyncClient,
    compliance_officer_token: str,
    seeded_hitl_tasks: List[HITLQueue],
) -> None:
    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.get(
        "/api/v1/hitl/tasks/pending?page=1&size=10", headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] >= 5
    assert len(data["items"]) >= 5
    assert data["page"] == 1

    response_filtered = await async_client.get(
        "/api/v1/hitl/tasks/pending?risk_category=AML_FLAG", headers=headers
    )
    assert response_filtered.status_code == status.HTTP_200_OK
    filtered_data = response_filtered.json()
    assert all(item["risk_category"] == "AML_FLAG" for item in filtered_data["items"])


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_access_hitl_endpoints(
    async_client: AsyncClient,
    normal_user_token: str,
    seeded_hitl_tasks: List[HITLQueue],
) -> None:
    headers = {"Authorization": f"Bearer {normal_user_token}"}

    response = await async_client.get("/api/v1/hitl/tasks/pending", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    claim_response = await async_client.post(
        f"/api/v1/hitl/tasks/{seeded_hitl_tasks[0].id}/claim", headers=headers
    )
    assert claim_response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_claim_and_resolve_task_creates_feedback_and_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
    compliance_officer_token: str,
    compliance_officer_user: User,
    seeded_hitl_tasks: List[HITLQueue],
) -> None:
    app.dependency_overrides[get_llm_client] = override_llm_client

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}
    target_task = seeded_hitl_tasks[0]

    claim_response = await async_client.post(
        f"/api/v1/hitl/tasks/{target_task.id}/claim", headers=headers
    )
    assert claim_response.status_code == status.HTTP_200_OK

    my_tasks_response = await async_client.get(
        "/api/v1/hitl/tasks/my-assignments", headers=headers
    )
    assert my_tasks_response.status_code == status.HTTP_200_OK
    assert any(t["id"] == target_task.id for t in my_tasks_response.json()["items"])

    resolve_payload = {
        "resolution_status": "APPROVED",
        "officer_notes": "Reviewed offline documentation. Cleared.",
        "action_taken": "MANUAL_APPROVAL",
        "generate_ai_feedback": True,
    }

    resolve_response = await async_client.post(
        f"/api/v1/hitl/tasks/{target_task.id}/resolve",
        json=resolve_payload,
        headers=headers,
    )
    assert resolve_response.status_code == status.HTTP_200_OK
    resolve_data = resolve_response.json()
    assert resolve_data["status"] == "RESOLVED"
    assert resolve_data["feedback_loop_generated"] is True

    await db_session.refresh(target_task)
    assert target_task.task_status.value == "APPROVED"
    assert target_task.resolution_notes == resolve_payload["officer_notes"]
    assert target_task.reviewer_id == compliance_officer_user.id

    query_audit = select(AuditLog).where(
        AuditLog.resource_id == target_task.resource_id
    )
    audit_result = await db_session.execute(query_audit)
    audit_logs = list(audit_result.scalars().all())

    hitl_log = next(
        (
            log
            for log in audit_logs
            if log.event_type.value == AuditEventType.HITL_APPROVAL.value
        ),
        None,
    )
    assert hitl_log is not None
    assert hitl_log.actor_id == compliance_officer_user.id
    assert hitl_log.new_state.get("ai_feedback_loop") is not None
    assert (
        hitl_log.new_state["ai_feedback_loop"]["learning_extraction"]["parsed_data"][
            "ai_was_correct"
        ]
        is False
    )

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_claim_conflict_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
    compliance_officer_token: str,
    admin_token: str,
    seeded_hitl_tasks: List[HITLQueue],
) -> None:
    target_task = seeded_hitl_tasks[1]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_claim = await async_client.post(
        f"/api/v1/hitl/tasks/{target_task.id}/claim", headers=admin_headers
    )
    assert admin_claim.status_code == status.HTTP_200_OK

    officer_headers = {"Authorization": f"Bearer {compliance_officer_token}"}
    officer_claim = await async_client.post(
        f"/api/v1/hitl/tasks/{target_task.id}/claim", headers=officer_headers
    )

    assert officer_claim.status_code == status.HTTP_409_CONFLICT
    assert "already claimed" in officer_claim.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_metrics_endpoint(
    async_client: AsyncClient,
    compliance_officer_token: str,
    seeded_hitl_tasks: List[HITLQueue],
) -> None:
    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.get("/api/v1/hitl/metrics", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    metrics = response.json()

    assert "status_counts" in metrics
    assert "PENDING_REVIEW" in metrics["status_counts"]
    assert "active_sla_breaches" in metrics
    assert "pending_risk_distribution" in metrics
    assert "average_processing_time_seconds" in metrics
