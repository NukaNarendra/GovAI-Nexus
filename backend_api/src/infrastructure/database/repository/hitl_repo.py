import datetime
import uuid
import hashlib
import json
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, func, asc, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    PriorityLevel,
    RiskCategory,
)
from src.infrastructure.database.models.audit_log import (
    AuditLog,
    AuditEventType,
    ActionSeverity,
    ActorType,
)
from src.infrastructure.database.repository.base import BaseRepository, PaginationResult


class HITLRepositoryError(Exception):
    pass


class TaskAlreadyClaimedError(HITLRepositoryError):
    pass


class HITLRepository(BaseRepository[HITLQueue, Any, Any]):
    def __init__(self):
        super().__init__(HITLQueue)

    async def get_pending_tasks(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 50,
        risk_category: Optional[RiskCategory] = None,
        priority: Optional[PriorityLevel] = None,
    ) -> PaginationResult[HITLQueue]:
        filters = [HITLQueue.task_status == HITLTaskStatus.PENDING_REVIEW]

        if risk_category:
            filters.append(HITLQueue.risk_category == risk_category)
        if priority:
            filters.append(HITLQueue.priority == priority)

        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="created_at",
            sort_order="asc",
            load_relations=["audit_log"],
        )

    async def get_tasks_assigned_to_user(
        self,
        db: AsyncSession,
        user_id: str,
        include_resolved: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> PaginationResult[HITLQueue]:
        filters = [HITLQueue.reviewer_id == user_id]

        if not include_resolved:
            filters.append(HITLQueue.task_status == HITLTaskStatus.UNDER_REVIEW)

        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="claimed_at",
            sort_order="desc",
        )

    async def claim_task_with_lock(
        self, db: AsyncSession, task_id: str, user_id: str
    ) -> HITLQueue:
        query = (
            select(HITLQueue)
            .where(HITLQueue.id == task_id)
            .with_for_update(nowait=True)
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()

        if not task:
            raise HITLRepositoryError(f"Task {task_id} not found")

        if (
            task.task_status != HITLTaskStatus.PENDING_REVIEW
            and task.task_status != HITLTaskStatus.ESCALATED
        ):
            if task.reviewer_id == user_id:
                return task
            raise TaskAlreadyClaimedError(
                f"Task {task_id} is already claimed by another user"
            )

        task.claim_task(user_id)
        db.add(task)
        await db.flush()

        # 🚀 FIX: Manually generate the ID, Timestamp, and Hash to bypass the Catch-22
        log_id = str(uuid.uuid4())
        log_timestamp = datetime.datetime.utcnow()
        action_details = "Task claimed for review"
        new_state = {
            "status": HITLTaskStatus.UNDER_REVIEW.value,
            "reviewer_id": user_id,
        }

        # Fetch the previous hash
        hash_query = (
            select(AuditLog.cryptographic_hash)
            .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
            .limit(1)
        )
        hash_result = await db.execute(hash_query)
        last_hash = hash_result.scalar_one_or_none() or "GENESIS_BLOCK_00000000"

        # Perform the SHA-256 hash in Python memory BEFORE passing to AuditLog
        hash_seed = f"{log_id}{action_details}{json.dumps(new_state)}{last_hash}"
        crypto_hash = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()

        audit_log = AuditLog(
            id=log_id,
            timestamp=log_timestamp,
            event_type=AuditEventType.HITL_OVERRIDE,
            severity=ActionSeverity.INFO,
            actor_id=user_id,
            actor_type=ActorType.HUMAN_USER,
            resource_id=task.id,
            resource_type="HITL_QUEUE",
            action_details=action_details,
            new_state=new_state,
            previous_hash=last_hash,
            cryptographic_hash=crypto_hash,
            is_tampered=False,
        )

        db.add(audit_log)
        await db.flush()

        return task

    async def resolve_task_and_audit(
        self,
        db: AsyncSession,
        task_id: str,
        user_id: str,
        status: HITLTaskStatus,
        notes: str,
        action: str,
    ) -> HITLQueue:
        task = await self.get_or_fail(db, task_id)

        if task.reviewer_id != user_id:
            raise HITLRepositoryError(
                "User cannot resolve a task they have not claimed"
            )

        old_state = task.to_dict()
        task.resolve_task(user_id, status, notes, action)
        new_state = task.to_dict()

        db.add(task)

        event_type = (
            AuditEventType.HITL_APPROVAL
            if status == HITLTaskStatus.APPROVED
            else AuditEventType.HITL_OVERRIDE
        )

        # 🚀 FIX: Manually generate the ID, Timestamp, and Hash to bypass the Catch-22
        log_id = str(uuid.uuid4())
        log_timestamp = datetime.datetime.utcnow()
        action_details = (
            f"HITL task resolved with status {status.value}. Notes: {notes}"
        )

        query = (
            select(AuditLog.cryptographic_hash)
            .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
            .limit(1)
        )
        hash_result = await db.execute(query)
        last_hash = hash_result.scalar_one_or_none() or "GENESIS_BLOCK_00000000"

        # Perform the SHA-256 hash in Python memory BEFORE passing to AuditLog
        hash_seed = f"{log_id}{action_details}{json.dumps(new_state)}{last_hash}"
        crypto_hash = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()

        audit_log = AuditLog(
            id=log_id,
            timestamp=log_timestamp,
            event_type=event_type,
            severity=ActionSeverity.HIGH,
            actor_id=user_id,
            actor_type=ActorType.HUMAN_USER,
            resource_id=task.resource_id,
            resource_type=task.resource_type,
            action_details=action_details,
            old_state=old_state,
            new_state=new_state,
            previous_hash=last_hash,
            cryptographic_hash=crypto_hash,
            is_tampered=False,
        )

        db.add(audit_log)
        task.audit_log_id = audit_log.id

        await db.flush()
        await db.refresh(task)
        return task

    async def get_queue_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        status_query = select(HITLQueue.task_status, func.count(HITLQueue.id)).group_by(
            HITLQueue.task_status
        )
        status_result = await db.execute(status_query)
        status_counts = {
            row[0].value if hasattr(row[0], "value") else row[0]: row[1]
            for row in status_result.all()
        }

        breach_query = select(func.count(HITLQueue.id)).where(
            and_(
                HITLQueue.task_status.in_(
                    [HITLTaskStatus.PENDING_REVIEW, HITLTaskStatus.UNDER_REVIEW]
                ),
                HITLQueue.is_sla_breached == True,
            )
        )
        breach_result = await db.execute(breach_query)
        sla_breaches = breach_result.scalar_one()

        risk_query = (
            select(HITLQueue.risk_category, func.count(HITLQueue.id))
            .where(HITLQueue.task_status.in_([HITLTaskStatus.PENDING_REVIEW, HITLTaskStatus.UNDER_REVIEW]))
            .group_by(HITLQueue.risk_category)
        )
        risk_result = await db.execute(risk_query)
        risk_distribution = {
            row[0].value if hasattr(row[0], "value") else row[0]: row[1]
            for row in risk_result.all()
        }

        avg_time_query = select(
            func.avg(
                func.extract("epoch", HITLQueue.resolved_at)
                - func.extract("epoch", HITLQueue.claimed_at)
            )
        ).where(HITLQueue.resolved_at.isnot(None))
        time_result = await db.execute(avg_time_query)
        avg_processing_time = time_result.scalar_one_or_none() or 0.0

        return {
            "status_counts": status_counts,
            "active_sla_breaches": sla_breaches,
            "pending_risk_distribution": risk_distribution,
            "average_processing_time_seconds": float(avg_processing_time),
            "total_pending": status_counts.get(HITLTaskStatus.PENDING_REVIEW.value, 0),
        }

    async def auto_expire_breached_tasks(self, db: AsyncSession) -> int:
        query = (
            update(HITLQueue)
            .where(
                and_(
                    HITLQueue.task_status == HITLTaskStatus.PENDING_REVIEW,
                    HITLQueue.deadline_at < datetime.datetime.utcnow(),
                    HITLQueue.priority != PriorityLevel.CRITICAL,
                )
            )
            .values(
                task_status=HITLTaskStatus.EXPIRED,
                is_sla_breached=True,
                resolution_notes="SYSTEM AUTOMATION: Task expired due to SLA breach.",
            )
        )

        result = await db.execute(query)
        await db.flush()
        return result.rowcount


hitl_repository = HITLRepository()
