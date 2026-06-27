import uuid
import datetime
import asyncio
import pytest
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
    ActorType,
)
from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    RiskCategory,
    PriorityLevel,
)
from src.infrastructure.database.models.user import User
from src.infrastructure.database.repository.audit_repo import audit_repository
from src.infrastructure.database.repository.hitl_repo import (
    hitl_repository,
    TaskAlreadyClaimedError,
)


@pytest.mark.asyncio
async def test_audit_repo_secure_append_and_chain_integrity(
    db_session: AsyncSession,
) -> None:
    logs = []
    actor_id = f"USR_{uuid.uuid4().hex[:8]}"

    for i in range(5):
        log = AuditLog(
            event_type=AuditEventType.USER_AUTHENTICATION,
            severity=ActionSeverity.INFO,
            actor_id=actor_id,
            actor_type=ActorType.HUMAN_USER,
            resource_id=f"RES_{i}",
            resource_type="SYSTEM",
            action_details=f"Test action {i}",
            correlation_id=str(uuid.uuid4()),
        )
        saved_log = await audit_repository.append_secure_log(db_session, log)
        logs.append(saved_log)
        await asyncio.sleep(0.01)

    assert len(logs) == 5
    assert logs[0].previous_hash == "0" * 64
    for i in range(1, 5):
        assert logs[i].previous_hash == logs[i - 1].cryptographic_hash
        assert logs[i].verify_integrity() is True

    integrity_result = await audit_repository.verify_chain_integrity(
        db_session, days_back=1
    )
    assert integrity_result["status"] == "valid"
    assert integrity_result["scanned_records"] >= 5
    assert len(integrity_result["corrupted_ids"]) == 0


@pytest.mark.asyncio
async def test_audit_repo_detects_tampered_data(db_session: AsyncSession) -> None:
    actor_id = f"USR_{uuid.uuid4().hex[:8]}"
    log1 = AuditLog(
        event_type=AuditEventType.SYSTEM_CONFIGURATION_CHANGED,
        severity=ActionSeverity.HIGH,
        actor_id=actor_id,
        actor_type=ActorType.SYSTEM_PROCESS,
        action_details="Initial state",
    )
    saved_log1 = await audit_repository.append_secure_log(db_session, log1)

    log2 = AuditLog(
        event_type=AuditEventType.SYSTEM_CONFIGURATION_CHANGED,
        severity=ActionSeverity.HIGH,
        actor_id=actor_id,
        actor_type=ActorType.SYSTEM_PROCESS,
        action_details="Subsequent state",
    )
    saved_log2 = await audit_repository.append_secure_log(db_session, log2)

    await db_session.execute(
        update(AuditLog)
        .where(AuditLog.id == saved_log1.id)
        .values(action_details="Maliciously altered state")
    )
    await db_session.commit()

    integrity_result = await audit_repository.verify_chain_integrity(
        db_session, days_back=1
    )
    assert integrity_result["status"] == "compromised"
    assert saved_log1.id in integrity_result["corrupted_ids"]
    assert saved_log2.id in integrity_result["corrupted_ids"]


@pytest.mark.asyncio
async def test_audit_repo_pagination_and_filtering(db_session: AsyncSession) -> None:
    actor_id = f"USR_{uuid.uuid4().hex[:8]}"
    for i in range(15):
        log = AuditLog(
            event_type=AuditEventType.AI_DECISION_EXECUTED
            if i % 2 == 0
            else AuditEventType.HITL_APPROVAL,
            severity=ActionSeverity.HIGH,
            actor_id=actor_id,
            actor_type=ActorType.AI_AGENT if i % 2 == 0 else ActorType.HUMAN_USER,
            action_details=f"Paginating test {i}",
        )
        await audit_repository.append_secure_log(db_session, log)

    paginated_results = await audit_repository.get_logs_by_actor(
        db_session, actor_id=actor_id, page=1, size=10
    )
    assert paginated_results.total == 15
    assert len(paginated_results.items) == 10
    assert paginated_results.has_next is True

    page_2 = await audit_repository.get_logs_by_actor(
        db_session, actor_id=actor_id, page=2, size=10
    )
    assert len(page_2.items) == 5
    assert page_2.has_next is False


@pytest.mark.asyncio
async def test_hitl_repo_concurrent_task_claiming(db_session: AsyncSession) -> None:
    task = HITLQueue(
        risk_category=RiskCategory.AML_FLAG,
        priority=PriorityLevel.HIGH,
        agent_id="AGENT_X",
        model_version="v1",
        ai_confidence_score=0.45,
        resource_id=f"RES_{uuid.uuid4().hex[:8]}",
        resource_type="WIRE_TRANSFER",
        transaction_context={},
        compliance_flags={},
        ai_reasoning="Suspicious activity",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    user1_id = f"USR_{uuid.uuid4().hex[:8]}"
    user2_id = f"USR_{uuid.uuid4().hex[:8]}"
    user3_id = f"USR_{uuid.uuid4().hex[:8]}"

    async def attempt_claim(user_id: str) -> bool:
        from src.infrastructure.database.session import db_manager

        async for session in db_manager.get_session():
            try:
                await hitl_repository.claim_task_with_lock(session, task.id, user_id)
                await session.commit()
                return True
            except TaskAlreadyClaimedError:
                await session.rollback()
                return False
            except Exception:
                await session.rollback()
                return False

            return False

    results = await asyncio.gather(
        attempt_claim(user1_id), attempt_claim(user2_id), attempt_claim(user3_id)
    )

    success_count = sum(1 for r in results if r is True)
    assert success_count == 1

    await db_session.refresh(task)
    assert task.task_status == HITLTaskStatus.UNDER_REVIEW
    assert task.reviewer_id in [user1_id, user2_id, user3_id]


@pytest.mark.asyncio
async def test_hitl_repo_resolve_task_creates_audit_log(
    db_session: AsyncSession,
) -> None:
    task = HITLQueue(
        risk_category=RiskCategory.SANCTIONS_MATCH,
        priority=PriorityLevel.CRITICAL,
        agent_id="AGENT_Y",
        model_version="v1",
        ai_confidence_score=0.99,
        resource_id=f"RES_{uuid.uuid4().hex[:8]}",
        resource_type="ACCOUNT_OPENING",
        transaction_context={"amount": 50000},
        compliance_flags={"sanctions": True},
        ai_reasoning="Direct match",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    user_id = f"USR_{uuid.uuid4().hex[:8]}"
    claimed_task = await hitl_repository.claim_task_with_lock(
        db_session, task.id, user_id
    )
    await db_session.commit()

    resolved_task = await hitl_repository.resolve_task_and_audit(
        db_session,
        task_id=claimed_task.id,
        user_id=user_id,
        status=HITLTaskStatus.REJECTED,
        notes="Confirmed sanctions match. Rejecting.",
        action="HARD_BLOCK_ACCOUNT",
    )
    await db_session.commit()

    assert resolved_task.task_status == HITLTaskStatus.REJECTED
    assert resolved_task.audit_log_id is not None

    audit_log = await audit_repository.get(db_session, resolved_task.audit_log_id)
    assert audit_log is not None
    assert audit_log.event_type == AuditEventType.HITL_OVERRIDE
    assert audit_log.actor_id == user_id
    assert audit_log.resource_id == task.resource_id


@pytest.mark.asyncio
async def test_hitl_repo_auto_expire_breached_tasks(db_session: AsyncSession) -> None:
    now = datetime.datetime.utcnow()
    past_deadline = now - datetime.timedelta(hours=1)
    future_deadline = now + datetime.timedelta(hours=1)

    task1 = HITLQueue(
        risk_category=RiskCategory.KYC_ANOMALY,
        priority=PriorityLevel.MEDIUM,
        agent_id="A",
        model_version="1",
        ai_confidence_score=0.5,
        resource_id="R1",
        resource_type="T",
        transaction_context={},
        compliance_flags={},
        ai_reasoning="reason",
        deadline_at=past_deadline,
    )
    task2 = HITLQueue(
        risk_category=RiskCategory.KYC_ANOMALY,
        priority=PriorityLevel.CRITICAL,
        agent_id="A",
        model_version="1",
        ai_confidence_score=0.5,
        resource_id="R2",
        resource_type="T",
        transaction_context={},
        compliance_flags={},
        ai_reasoning="reason",
        deadline_at=past_deadline,
    )
    task3 = HITLQueue(
        risk_category=RiskCategory.KYC_ANOMALY,
        priority=PriorityLevel.LOW,
        agent_id="A",
        model_version="1",
        ai_confidence_score=0.5,
        resource_id="R3",
        resource_type="T",
        transaction_context={},
        compliance_flags={},
        ai_reasoning="reason",
        deadline_at=future_deadline,
    )

    db_session.add_all([task1, task2, task3])
    await db_session.commit()

    expired_count = await hitl_repository.auto_expire_breached_tasks(db_session)

    await db_session.refresh(task1)
    await db_session.refresh(task2)
    await db_session.refresh(task3)

    assert task1.task_status == HITLTaskStatus.EXPIRED
    assert task1.is_sla_breached is True

    assert task2.task_status == HITLTaskStatus.PENDING_REVIEW
    assert task2.is_sla_breached is False

    assert task3.task_status == HITLTaskStatus.PENDING_REVIEW
