import uuid
import pytest
from httpx import AsyncClient
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import status

from src.infrastructure.database.models.hitl_queue import HITLQueue, HITLTaskStatus
from src.infrastructure.database.models.transaction_record import (
    TransactionRecord,
    TransactionState,
    TransactionType,
)


@pytest.mark.asyncio
async def test_transaction_hitl_approval_and_manual_execution(
    async_client: AsyncClient,
    db_session: AsyncSession,
    compliance_officer_token: str,
    compliance_officer_user: User,
) -> None:
    transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
    reference_id = f"REF_{uuid.uuid4().hex[:10].upper()}"
    source_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"
    dest_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"

    tx_record = TransactionRecord(
        id=transaction_id,
        reference_id=reference_id,
        status=TransactionState.PENDING_COMPLIANCE,
        transaction_type=TransactionType.INTERNATIONAL_WIRE,
        source_entity_id=source_entity_id,
        source_account_id="ACC_SRC_999",
        source_country="USA",
        destination_entity_id=dest_entity_id,
        destination_account_id="ACC_DST_999",
        destination_country="ARE",
        amount=250000.00,
        currency="USD",
        ai_risk_score=65.0,
        ai_confidence_score=0.89,
        compliance_passed=False,
        requires_hitl=True,
        compliance_metadata={"trigger": "HIGH_VALUE_TRANSFER_MEDIUM_RISK_JURISDICTION"},
    )
    db_session.add(tx_record)
    await db_session.flush()

    evaluation_payload: Dict[str, Any] = {
        "transaction_payload": {
            "transaction_id": transaction_id,
            "amount": 250000.00,
            "currency": "USD",
            "source_account_id": "ACC_SRC_999",
            "destination_account_id": "ACC_DST_999",
            "source_country": "USA",
            "destination_country": "ARE",
            "transaction_type": "INTERNATIONAL_WIRE",
        },
        "source_profile": {
            "entity_id": source_entity_id,
            "entity_name": "Global Tech Holdings",
            "country_of_incorporation": "USA",
            "industry_code": "511210",
            "historical_average_volume": 500000.00,
            "account_created_timestamp": 1550000000.0,
            "recent_transactions": [],
        },
        "destination_profile": {
            "entity_id": dest_entity_id,
            "entity_name": "Desert Innovations LLC",
            "country_of_incorporation": "ARE",
            "industry_code": "511210",
            "historical_average_volume": 100000.00,
            "account_created_timestamp": 1650000000.0,
            "recent_transactions": [],
        },
    }

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    eval_response = await async_client.post(
        "/api/v1/gateway/transactions/evaluate",
        json=evaluation_payload,
        headers=headers,
    )

    assert eval_response.status_code == status.HTTP_200_OK
    eval_data = eval_response.json()
    assert eval_data["status"] == "HOLD_FOR_REVIEW"

    query_hitl = select(HITLQueue).where(HITLQueue.resource_id == transaction_id)
    hitl_result = await db_session.execute(query_hitl)
    hitl_task = hitl_result.scalar_one_or_none()
    assert hitl_task is not None
    task_id = hitl_task.id

    claim_response = await async_client.post(
        f"/api/v1/hitl/tasks/{task_id}/claim", headers=headers
    )
    assert claim_response.status_code == status.HTTP_200_OK

    resolve_payload = {
        "resolution_status": "APPROVED",
        "officer_notes": "Reviewed underlying invoice and contract. Payment aligns with known business operations. Risk score elevated solely due to jurisdiction (UAE). Approved.",
        "action_taken": "MANUALLY_CLEARED_COMPLIANCE",
        "generate_ai_feedback": False,
    }
    resolve_response = await async_client.post(
        f"/api/v1/hitl/tasks/{task_id}/resolve", json=resolve_payload, headers=headers
    )
    assert resolve_response.status_code == status.HTTP_200_OK

    tx_record.mark_compliance_cleared(
        risk_score=45.0,
        metadata={"cleared_by": compliance_officer_user.id, "hitl_task": task_id},
    )
    db_session.add(tx_record)
    await db_session.commit()
    await db_session.refresh(tx_record)

    assert tx_record.status == TransactionState.CLEARED

    exec_payload = {
        "transaction_id": transaction_id,
        "execution_reason": "Compliance cleared. Triggering final core banking settlement.",
        "force_override": False,
    }

    exec_response = await async_client.post(
        "/api/v1/execution/manual", json=exec_payload, headers=headers
    )

    assert exec_response.status_code == status.HTTP_200_OK
    exec_data = exec_response.json()

    assert exec_data["transaction_id"] == transaction_id
    assert exec_data["status"] == "EXECUTED"
    assert exec_data["core_banking_reference"] is not None
    assert exec_data["executed_at"] is not None

    await db_session.refresh(tx_record)
    assert tx_record.status == TransactionState.EXECUTED
    assert tx_record.core_banking_id == exec_data["core_banking_reference"]

    audit_response = await async_client.get(
        f"/api/v1/audit/logs?resource_id={transaction_id}", headers=headers
    )
    assert audit_response.status_code == status.HTTP_200_OK
    audit_data = audit_response.json()

    event_types = [item["event_type"] for item in audit_data["items"]]
    assert "AI_DECISION_EXECUTED" in event_types
    assert "HITL_APPROVAL" in event_types

    for item in audit_data["items"]:
        assert item["is_tampered"] is False
