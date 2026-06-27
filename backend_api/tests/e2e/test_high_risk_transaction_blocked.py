import uuid
import pytest
from httpx import AsyncClient
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status

from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
)


@pytest.mark.asyncio
async def test_transaction_auto_blocked_due_to_fatf_jurisdiction_and_velocity(
    async_client: AsyncClient, db_session: AsyncSession, compliance_officer_token: str
) -> None:
    transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
    source_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"
    dest_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"

    evaluation_payload: Dict[str, Any] = {
        "transaction_payload": {
            "transaction_id": transaction_id,
            "amount": 9500000.00,
            "currency": "USD",
            "source_account_id": "ACC_SOURCE_001",
            "destination_account_id": "ACC_DEST_001",
            "source_country": "USA",
            "destination_country": "PRK",
            "transaction_type": "INTERNATIONAL_WIRE",
            "purpose_code": "CAPITAL_INJECTION",
        },
        "source_profile": {
            "entity_id": source_entity_id,
            "entity_name": "Standard Logistics Corp",
            "country_of_incorporation": "USA",
            "industry_code": "423990",
            "historical_average_volume": 15000.00,
            "account_created_timestamp": 1609459200.0,
            "recent_transactions": [
                {
                    "transaction_id": "TXN_PAST_1",
                    "amount": 10000.00,
                    "timestamp": 1672531200.0,
                    "source_account": "ACC_SOURCE_001",
                },
                {
                    "transaction_id": "TXN_PAST_2",
                    "amount": 12000.00,
                    "timestamp": 1672617600.0,
                    "source_account": "ACC_SOURCE_001",
                },
                {
                    "transaction_id": "TXN_PAST_3",
                    "amount": 8000.00,
                    "timestamp": 1672704000.0,
                    "source_account": "ACC_SOURCE_001",
                },
            ],
        },
        "destination_profile": {
            "entity_id": dest_entity_id,
            "entity_name": "Frontier Import Export Ltd",
            "country_of_incorporation": "PRK",
            "industry_code": "5094",
            "historical_average_volume": 0.0,
            "account_created_timestamp": 1704067200.0,
            "recent_transactions": [],
        },
    }

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.post(
        "/api/v1/gateway/transactions/evaluate",
        json=evaluation_payload,
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert response_data["status"] == "BLOCK_TRANSACTION"
    assert response_data["requires_human_review"] is False
    assert response_data["governance_verdict"]["verdict"] == "REJECTED_AUTO"
    assert response_data["governance_verdict"]["requires_hard_block"] is True

    risk_assessment = response_data["governance_verdict"]["risk_assessment"]
    assert risk_assessment["risk_tier"] == "UNACCEPTABLE_RISK"
    assert risk_assessment["total_score"] >= 95.0

    aml_results = response_data["governance_verdict"]["aml_results"]
    assert aml_results["status"] == "BLOCKED_SANCTIONS"

    jurisdiction_violation = next(
        (
            v
            for v in aml_results["violations"]
            if v["violation_code"] == "HIGH_RISK_JURISDICTION"
        ),
        None,
    )
    assert jurisdiction_violation is not None
    assert jurisdiction_violation["severity"] == "CRITICAL"

    velocity_violation = next(
        (
            v
            for v in aml_results["violations"]
            if v["violation_code"] == "VOLUME_SPIKE_DETECTED"
        ),
        None,
    )
    assert velocity_violation is not None
    assert velocity_violation["severity"] == "HIGH"

    query_audit = (
        select(AuditLog)
        .where(AuditLog.resource_id == transaction_id)
        .order_by(AuditLog.timestamp.desc())
    )
    audit_result = await db_session.execute(query_audit)
    logs = list(audit_result.scalars().all())

    assert len(logs) >= 1
    primary_log = logs[0]
    assert primary_log.event_type == AuditEventType.AI_DECISION_EXECUTED
    assert primary_log.severity == ActionSeverity.HIGH
    assert "BLOCK_TRANSACTION" in primary_log.action_details
    assert "REJECTED_AUTO" in primary_log.action_details
    assert primary_log.actor_type.value == "AI_AGENT"

    assert primary_log.verify_integrity() is True


@pytest.mark.asyncio
async def test_transaction_auto_blocked_due_to_structuring_pattern(
    async_client: AsyncClient, db_session: AsyncSession, compliance_officer_token: str
) -> None:
    transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
    source_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"
    dest_entity_id = f"ENT_{uuid.uuid4().hex[:8].upper()}"

    import time

    now = time.time()

    evaluation_payload: Dict[str, Any] = {
        "transaction_payload": {
            "transaction_id": transaction_id,
            "amount": 9900.00,
            "currency": "USD",
            "source_account_id": "ACC_SOURCE_002",
            "destination_account_id": "ACC_DEST_002",
            "source_country": "USA",
            "destination_country": "GBR",
            "transaction_type": "INTERNATIONAL_WIRE",
            "purpose_code": "CONSULTING_FEE",
        },
        "source_profile": {
            "entity_id": source_entity_id,
            "entity_name": "Consulting Partners Group",
            "country_of_incorporation": "USA",
            "industry_code": "541611",
            "historical_average_volume": 45000.00,
            "account_created_timestamp": 1500000000.0,
            "recent_transactions": [
                {
                    "transaction_id": "TXN_PAST_1",
                    "amount": 9850.00,
                    "timestamp": now - 86400,
                    "source_account": "ACC_SOURCE_002",
                },
                {
                    "transaction_id": "TXN_PAST_2",
                    "amount": 9950.00,
                    "timestamp": now - 172800,
                    "source_account": "ACC_SOURCE_002",
                },
                {
                    "transaction_id": "TXN_PAST_3",
                    "amount": 9999.00,
                    "timestamp": now - 259200,
                    "source_account": "ACC_SOURCE_002",
                },
            ],
        },
        "destination_profile": {
            "entity_id": dest_entity_id,
            "entity_name": "UK Advisory Services",
            "country_of_incorporation": "GBR",
            "industry_code": "541611",
            "historical_average_volume": 120000.00,
            "account_created_timestamp": 1600000000.0,
            "recent_transactions": [],
        },
    }

    headers = {"Authorization": f"Bearer {compliance_officer_token}"}

    response = await async_client.post(
        "/api/v1/gateway/transactions/evaluate",
        json=evaluation_payload,
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()

    assert response_data["status"] == "BLOCK_TRANSACTION"
    assert response_data["governance_verdict"]["verdict"] == "REJECTED_AUTO"
    assert response_data["governance_verdict"]["requires_hard_block"] is True

    aml_results = response_data["governance_verdict"]["aml_results"]
    assert aml_results["status"] == "BLOCKED_STRUCTURING"

    structuring_violation = next(
        (
            v
            for v in aml_results["violations"]
            if v["violation_code"] == "STRUCTURING_DETECTED"
        ),
        None,
    )
    assert structuring_violation is not None
    assert structuring_violation["severity"] == "HIGH"
    assert structuring_violation["matched_data"]["count"] == 4

    audit_response = await async_client.get(
        f"/api/v1/audit/logs?resource_id={transaction_id}", headers=headers
    )
    assert audit_response.status_code == status.HTTP_200_OK
    audit_data = audit_response.json()
    assert audit_data["total"] == 1
    assert audit_data["items"][0]["is_tampered"] is False
    assert audit_data["items"][0]["cryptographic_hash"] is not None
