import pytest
import uuid
from typing import Dict, Any, AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status

from src.infrastructure.database.models.hitl_queue import HITLQueue, HITLTaskStatus
from src.infrastructure.database.models.audit_log import AuditLog, AuditEventType
from src.domain.ai_agents.orchestrator import AIAgentOrchestrator
from src.api.v1.endpoints.ai_gateway import get_orchestrator
from src.main import app


class MockOrchestratorForAPI:
    def __init__(self, should_require_hitl: bool = False, is_kyc: bool = True):
        self.should_require_hitl = should_require_hitl
        self.is_kyc = is_kyc
        self.agent_id = "MOCK_AGENT_API_TEST"

    async def process_kyc_onboarding(
        self, entity_payload: Dict[str, Any], historical_data: list
    ) -> Dict[str, Any]:
        verdict = "ROUTED_TO_HITL" if self.should_require_hitl else "APPROVED_AUTO"
        status_val = "PENDING_HITL" if self.should_require_hitl else "APPROVED"
        return {
            "orchestration_id": str(uuid.uuid4()),
            "timestamp": "2024-05-20T10:00:00Z",
            "final_onboarding_status": status_val,
            "ai_analysis": {
                "model_used": "mock-llama",
                "ai_confidence_score": 0.85 if self.should_require_hitl else 0.98,
                "primary_reasoning": "Mock reasoning generated during integration test",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            },
            "governance_decision": {
                "verdict": verdict,
                "requires_hard_block": False,
                "governance_notes": "Mock governance applied",
            },
            "requires_human_review": self.should_require_hitl,
        }

    async def process_wire_transfer(
        self,
        transaction_payload: Dict[str, Any],
        source_profile: Dict[str, Any],
        destination_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        verdict = "ROUTED_TO_HITL" if self.should_require_hitl else "APPROVED_AUTO"
        status_val = (
            "HOLD_FOR_REVIEW" if self.should_require_hitl else "EXECUTE_TRANSACTION"
        )
        return {
            "orchestration_id": str(uuid.uuid4()),
            "timestamp": "2024-05-20T10:00:00Z",
            "execution_directive": status_val,
            "ai_analysis": {
                "model_used": "mock-llama",
                "ai_confidence_score": 0.85 if self.should_require_hitl else 0.98,
                "investigator_notes": "Mock transaction logic generated during integration test",
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300,
                },
            },
            "governance_decision": {
                "verdict": verdict,
                "requires_hard_block": False,
                "governance_notes": "Mock governance applied",
            },
            "requires_human_review": self.should_require_hitl,
        }


def override_orchestrator_approved():
    return MockOrchestratorForAPI(should_require_hitl=False)


def override_orchestrator_hitl():
    return MockOrchestratorForAPI(should_require_hitl=True)


@pytest.fixture
def kyc_payload() -> Dict[str, Any]:
    return {
        "entity_payload": {
            "entity_id": f"ENT_{uuid.uuid4().hex[:8]}",
            "entity_name": "API Test Corp",
            "country_of_incorporation": "GBR",
            "industry_code": "511210",
            "beneficial_owners": ["Integration Tester"],
        },
        "historical_data": [],
    }


@pytest.fixture
def transaction_payload() -> Dict[str, Any]:
    return {
        "transaction_payload": {
            "transaction_id": f"TXN_{uuid.uuid4().hex[:12]}",
            "amount": 50000.0,
            "currency": "USD",
            "source_account_id": "ACC_1",
            "destination_account_id": "ACC_2",
            "source_country": "USA",
            "destination_country": "CAN",
            "transaction_type": "WIRE_TRANSFER",
        },
        "source_profile": {
            "entity_id": "ENT_1",
            "entity_name": "Source Corp",
            "country_of_incorporation": "USA",
            "historical_average_volume": 100000.0,
            "recent_transactions": [],
        },
        "destination_profile": {
            "entity_id": "ENT_2",
            "entity_name": "Dest Corp",
            "country_of_incorporation": "CAN",
            "historical_average_volume": 20000.0,
            "recent_transactions": [],
        },
    }


@pytest.mark.asyncio
async def test_kyc_onboarding_auto_approved_no_hitl_queue(
    async_client: AsyncClient,
    db_session: AsyncSession,
    normal_user_token: str,
    kyc_payload: Dict[str, Any],
) -> None:
    app.dependency_overrides[get_orchestrator] = override_orchestrator_approved

    headers = {"Authorization": f"Bearer {normal_user_token}"}
    response = await async_client.post(
        "/api/v1/gateway/kyc/onboard", json=kyc_payload, headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["requires_human_review"] is False

    entity_id = kyc_payload["entity_payload"]["entity_id"]
    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == entity_id)
    hitl_result = await db_session.execute(query_hitl)
    assert hitl_result.scalar_one_or_none() is None

    query_audit = select(AuditLog).where(AuditLog.resource_id == entity_id)
    audit_result = await db_session.execute(query_audit)
    audit_log = audit_result.scalar_one_or_none()
    assert audit_log is not None
    assert audit_log.event_type.value == AuditEventType.AI_DECISION_EXECUTED.value
    assert "APPROVED" in audit_log.action_details

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kyc_onboarding_routed_to_hitl_creates_queue_entry(
    async_client: AsyncClient,
    db_session: AsyncSession,
    normal_user_token: str,
    kyc_payload: Dict[str, Any],
) -> None:
    app.dependency_overrides[get_orchestrator] = override_orchestrator_hitl

    headers = {"Authorization": f"Bearer {normal_user_token}"}
    response = await async_client.post(
        "/api/v1/gateway/kyc/onboard", json=kyc_payload, headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "PENDING_HITL"
    assert data["requires_human_review"] is True

    entity_id = kyc_payload["entity_payload"]["entity_id"]
    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == entity_id)
    hitl_result = await db_session.execute(query_hitl)
    hitl_task = hitl_result.scalar_one_or_none()

    assert hitl_task is not None
    assert hitl_task.task_status.value == "PENDING_REVIEW"
    assert hitl_task.ai_confidence_score == 0.85

    query_audit = select(AuditLog).where(AuditLog.resource_id == entity_id)
    audit_result = await db_session.execute(query_audit)
    audit_log = audit_result.scalar_one_or_none()
    assert audit_log is not None
    assert "PENDING_HITL" in audit_log.action_details

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_transaction_evaluation_auto_executed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    normal_user_token: str,
    transaction_payload: Dict[str, Any],
) -> None:
    app.dependency_overrides[get_orchestrator] = override_orchestrator_approved

    headers = {"Authorization": f"Bearer {normal_user_token}"}
    response = await async_client.post(
        "/api/v1/gateway/transactions/evaluate",
        json=transaction_payload,
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "EXECUTE_TRANSACTION"
    assert data["requires_human_review"] is False

    txn_id = transaction_payload["transaction_payload"]["transaction_id"]
    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == txn_id)
    hitl_result = await db_session.execute(query_hitl)
    assert hitl_result.scalar_one_or_none() is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gateway_endpoints_enforce_authentication(
    async_client: AsyncClient, kyc_payload: Dict[str, Any]
) -> None:
    response = await async_client.post("/api/v1/gateway/kyc/onboard", json=kyc_payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response_invalid = await async_client.post(
        "/api/v1/gateway/kyc/onboard",
        json=kyc_payload,
        headers={"Authorization": "Bearer invalid_token_format"},
    )
    assert response_invalid.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_gateway_payload_validation_failures(
    async_client: AsyncClient, normal_user_token: str
) -> None:
    headers = {"Authorization": f"Bearer {normal_user_token}"}
    invalid_payload = {"historical_data": []}

    response = await async_client.post(
        "/api/v1/gateway/kyc/onboard", json=invalid_payload, headers=headers
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "entity_payload" in str(data["detail"])
