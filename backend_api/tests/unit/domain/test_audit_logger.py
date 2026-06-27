import pytest
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
    ActorType,
)
from src.domain.audit.logger_service import (
    PIIScrubber,
    AuditLoggerService,
    correlation_id_ctx,
    actor_id_ctx,
    actor_type_ctx,
)


@pytest.fixture
def pii_scrubber() -> PIIScrubber:
    return PIIScrubber()


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_worm_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.append_immutable_record = AsyncMock(side_effect=lambda db, log: log)
    return storage


@pytest.fixture
def audit_service(
    mock_repo: AsyncMock, mock_worm_storage: AsyncMock
) -> AuditLoggerService:
    return AuditLoggerService(repository=mock_repo, worm_storage=mock_worm_storage)


def test_pii_scrubber_string_email(pii_scrubber: PIIScrubber) -> None:
    raw_text = "Contact user at john.doe@example.com for details."
    scrubbed = pii_scrubber.scrub_string(raw_text)
    assert scrubbed == "Contact user at [EMAIL_REDACTED] for details."


def test_pii_scrubber_string_ssn(pii_scrubber: PIIScrubber) -> None:
    raw_text = "User SSN is 123-45-6789 verified."
    scrubbed = pii_scrubber.scrub_string(raw_text)
    assert scrubbed == "User SSN is [SSN_REDACTED] verified."


def test_pii_scrubber_string_credit_card(pii_scrubber: PIIScrubber) -> None:
    raw_text = "Charged card 4532 1234 5678 9012 successfully."
    scrubbed = pii_scrubber.scrub_string(raw_text)
    assert scrubbed == "Charged card [CARD_REDACTED] successfully."


def test_pii_scrubber_dict_keys(pii_scrubber: PIIScrubber) -> None:
    raw_data = {
        "user_id": "U123",
        "password": "supersecretpassword",
        "cvv_code": "123",
        "public_profile": "developer",
    }
    scrubbed = pii_scrubber.scrub_dict(raw_data)
    assert scrubbed["user_id"] == "U123"
    assert scrubbed["password"] == "[REDACTED]"
    assert scrubbed["cvv_code"] == "[REDACTED]"
    assert scrubbed["public_profile"] == "developer"


def test_pii_scrubber_nested_dict(pii_scrubber: PIIScrubber) -> None:
    raw_data = {
        "transaction": {
            "amount": 500,
            "sender": {
                "name": "Alice",
                "secret_token": "abc-123",
                "passport_number": "P123456",
            },
        }
    }
    scrubbed = pii_scrubber.scrub_dict(raw_data)
    assert scrubbed["transaction"]["amount"] == 500
    assert scrubbed["transaction"]["sender"]["name"] == "Alice"
    assert scrubbed["transaction"]["sender"]["secret_token"] == "[REDACTED]"
    assert scrubbed["transaction"]["sender"]["passport_number"] == "[REDACTED]"


def test_pii_scrubber_list_of_dicts(pii_scrubber: PIIScrubber) -> None:
    raw_data = [{"id": 1, "ssn": "000-00-0000"}, {"id": 2, "tax_id": "99999"}]
    scrubbed = pii_scrubber.scrub_list(raw_data)
    assert scrubbed[0]["id"] == 1
    assert scrubbed[0]["ssn"] == "[REDACTED]"
    assert scrubbed[1]["id"] == 2
    assert scrubbed[1]["tax_id"] == "[REDACTED]"


def test_pii_scrubber_mixed_types(pii_scrubber: PIIScrubber) -> None:
    raw_data = {
        "metadata": ["User email is test@test.com", {"private_key": "rsa-key-data"}]
    }
    scrubbed = pii_scrubber.scrub_dict(raw_data)
    assert scrubbed["metadata"][0] == "User email is [EMAIL_REDACTED]"
    assert scrubbed["metadata"][1]["private_key"] == "[REDACTED]"


def test_audit_log_model_hash_calculation() -> None:
    log = AuditLog(
        id="LOG_1",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        event_type=AuditEventType.USER_AUTHENTICATION,
        actor_id="U_1",
        actor_type=ActorType.HUMAN_USER,
        resource_id="R_1",
        action_details="Login success",
        old_state=None,
        new_state={"ip": "127.0.0.1"},
    )
    hash_val = log.calculate_hash("PREV_HASH")
    assert hash_val is not None
    assert len(hash_val) == 64
    assert hash_val == log.calculate_hash("PREV_HASH")
    assert hash_val != log.calculate_hash("DIFFERENT_HASH")


def test_audit_log_model_seal_log() -> None:
    log = AuditLog(
        id="LOG_1",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        event_type=AuditEventType.USER_AUTHENTICATION,
        actor_id="U_1",
        actor_type=ActorType.HUMAN_USER,
        resource_id="R_1",
        action_details="Login success",
    )
    log.seal_log("PREVIOUS_HASH_123")
    assert log.previous_hash == "PREVIOUS_HASH_123"
    assert log.cryptographic_hash is not None
    assert log.verify_integrity() is True


def test_audit_log_model_verify_integrity_tampered() -> None:
    log = AuditLog(
        id="LOG_1",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        event_type=AuditEventType.USER_AUTHENTICATION,
        actor_id="U_1",
        actor_type=ActorType.HUMAN_USER,
        resource_id="R_1",
        action_details="Login success",
    )
    log.seal_log("PREV")
    log.action_details = "Login failed"
    assert log.verify_integrity() is False
    assert log.is_tampered is True


def test_create_ai_execution_log() -> None:
    tokens = {"prompt": 100, "completion": 50}
    log = AuditLog.create_ai_execution_log(
        agent_id="AGENT_X",
        action="APPROVE_TXN",
        target_resource="TXN_999",
        payload={"amt": 1000},
        model_version="llama-3",
        tokens_used=tokens,
    )
    assert log.event_type == AuditEventType.AI_DECISION_EXECUTED
    assert log.actor_id == "AGENT_X"
    assert log.actor_type == ActorType.AI_AGENT
    assert log.resource_id == "TXN_999"
    assert log.ai_prompt_tokens == 100
    assert log.ai_completion_tokens == 50


def test_create_hitl_override_log() -> None:
    log = AuditLog.create_hitl_override_log(
        officer_id="OFFICER_1",
        original_agent_id="AGENT_X",
        resource_id="TXN_999",
        override_reason="Offline verification",
        old_data={"status": "PENDING"},
        new_data={"status": "APPROVED"},
    )
    assert log.event_type == AuditEventType.HITL_OVERRIDE
    assert log.severity == ActionSeverity.CRITICAL
    assert log.actor_id == "OFFICER_1"
    assert log.actor_type == ActorType.HUMAN_USER
    assert log.old_state["status"] == "PENDING"
    assert log.new_state["status"] == "APPROVED"


def test_audit_service_context_management(audit_service: AuditLoggerService) -> None:
    audit_service.set_context("CORR_1", "ACTOR_1", ActorType.SYSTEM_PROCESS)
    assert correlation_id_ctx.get() == "CORR_1"
    assert actor_id_ctx.get() == "ACTOR_1"
    assert actor_type_ctx.get() == ActorType.SYSTEM_PROCESS

    audit_service.set_context("CORR_2", "ACTOR_2", ActorType.HUMAN_USER)
    assert audit_service.get_correlation_id() == "CORR_2"


def test_audit_service_get_correlation_id_generates_new(
    audit_service: AuditLoggerService,
) -> None:
    correlation_id_ctx.set("")
    cid = audit_service.get_correlation_id()
    assert cid is not None
    assert len(cid) > 10
    assert correlation_id_ctx.get() == cid


@pytest.mark.asyncio
async def test_log_ai_execution(audit_service: AuditLoggerService) -> None:
    db_mock = AsyncMock()
    payload = {"account": "A1", "amount": 500}
    ai_analysis = {
        "model_used": "v1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    log = await audit_service.log_ai_execution(
        db=db_mock,
        agent_id="AGENT_1",
        resource_id="RES_1",
        resource_type="TYPE_1",
        execution_directive="BLOCK_TRANSACTION",
        payload=payload,
        ai_analysis=ai_analysis,
        governance_verdict="REJECTED_AUTO",
    )

    assert log.event_type == AuditEventType.AI_DECISION_EXECUTED
    assert log.severity == ActionSeverity.HIGH
    assert log.actor_id == "AGENT_1"
    assert log.ai_model_version == "v1"
    assert log.ai_prompt_tokens == 10
    assert log.new_state == payload
    audit_service.worm_storage.append_immutable_record.assert_called_once()


@pytest.mark.asyncio
async def test_log_hitl_resolution_approved(audit_service: AuditLoggerService) -> None:
    db_mock = AsyncMock()
    log = await audit_service.log_hitl_resolution(
        db=db_mock,
        officer_id="OFF_1",
        task_id="TASK_1",
        resource_id="RES_1",
        resolution_status="APPROVED",
        officer_notes="Looks good",
        ai_learning_feedback=None,
    )
    assert log.event_type == AuditEventType.HITL_APPROVAL
    assert log.severity == ActionSeverity.HIGH
    assert log.actor_id == "OFF_1"
    assert log.new_state["new_status"] == "APPROVED"


@pytest.mark.asyncio
async def test_log_hitl_resolution_rejected(audit_service: AuditLoggerService) -> None:
    db_mock = AsyncMock()
    log = await audit_service.log_hitl_resolution(
        db=db_mock,
        officer_id="OFF_1",
        task_id="TASK_1",
        resource_id="RES_1",
        resolution_status="REJECTED",
        officer_notes="Fraud suspected",
        ai_learning_feedback={"correction": "block next time"},
    )
    assert log.event_type == AuditEventType.HITL_OVERRIDE
    assert log.new_state["new_status"] == "REJECTED"
    assert log.new_state["ai_feedback_loop"] is not None


@pytest.mark.asyncio
async def test_log_compliance_violation_critical(
    audit_service: AuditLoggerService,
) -> None:
    db_mock = AsyncMock()
    log = await audit_service.log_compliance_violation(
        db=db_mock,
        resource_id="RES_1",
        resource_type="TXN",
        violation_codes=["SANCTIONS_MATCH"],
        risk_score=95.0,
        system_notes="OFAC Hit",
    )
    assert log.event_type == AuditEventType.COMPLIANCE_RULE_TRIGGERED
    assert log.severity == ActionSeverity.CRITICAL
    assert log.new_state["calculated_risk"] == 95.0


@pytest.mark.asyncio
async def test_log_compliance_violation_high(audit_service: AuditLoggerService) -> None:
    db_mock = AsyncMock()
    log = await audit_service.log_compliance_violation(
        db=db_mock,
        resource_id="RES_1",
        resource_type="TXN",
        violation_codes=["VELOCITY_SPIKE"],
        risk_score=75.0,
        system_notes="Volume high",
    )
    assert log.event_type == AuditEventType.COMPLIANCE_RULE_TRIGGERED
    assert log.severity == ActionSeverity.HIGH
    assert log.new_state["calculated_risk"] == 75.0


@pytest.mark.asyncio
async def test_log_security_event_scrubs_ip(audit_service: AuditLoggerService) -> None:
    db_mock = AsyncMock()
    log = await audit_service.log_security_event(
        db=db_mock,
        user_id="U_1",
        event_type=AuditEventType.USER_AUTHENTICATION,
        details="Login success",
        ip_address="192.168.1.1",
    )
    assert log.event_type == AuditEventType.USER_AUTHENTICATION
    assert log.severity == ActionSeverity.INFO
    assert log.new_state["ip_address"] == "192.168.1.1"
