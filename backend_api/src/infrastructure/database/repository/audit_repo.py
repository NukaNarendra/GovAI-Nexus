import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models.audit_log import (
    AuditLog,
    ActionSeverity,
    ActorType,
    AuditEventType,
)
from src.infrastructure.database.repository.base import BaseRepository, PaginationResult


class AuditLogIntegrityError(Exception):
    pass


class AuditLogRepository(BaseRepository[AuditLog, Any, Any]):
    def __init__(self):
        super().__init__(AuditLog)

    async def append_secure_log(
        self, db: AsyncSession, log_entry: AuditLog
    ) -> AuditLog:
        query = (
            select(AuditLog.cryptographic_hash)
            .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
            .limit(1)
        )
        result = await db.execute(query)
        last_hash = result.scalar_one_or_none()

        log_entry.seal_log(prev_hash=last_hash)

        db.add(log_entry)
        await db.flush()
        await db.refresh(log_entry)
        return log_entry

    async def verify_chain_integrity(
        self, db: AsyncSession, days_back: int = 7
    ) -> Dict[str, Any]:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)

        query = (
            select(AuditLog)
            .where(AuditLog.timestamp >= cutoff_date)
            .order_by(asc(AuditLog.timestamp), asc(AuditLog.id))
        )
        result = await db.execute(query)
        logs = list(result.scalars().all())

        if not logs:
            return {"status": "valid", "scanned_records": 0, "corrupted_ids": []}

        corrupted_ids = []
        expected_prev_hash = logs[0].previous_hash

        for log in logs:
            if log.previous_hash != expected_prev_hash:
                corrupted_ids.append(log.id)
                log.is_tampered = True
                db.add(log)

            if not log.verify_integrity():
                corrupted_ids.append(log.id)

            expected_prev_hash = log.cryptographic_hash

        if corrupted_ids:
            await db.flush()
            return {
                "status": "compromised",
                "scanned_records": len(logs),
                "corrupted_ids": corrupted_ids,
                "message": "Cryptographic chain validation failed. WORM storage may be compromised.",
            }

        return {"status": "valid", "scanned_records": len(logs), "corrupted_ids": []}

    async def get_logs_by_actor(
        self,
        db: AsyncSession,
        actor_id: str,
        actor_type: Optional[ActorType] = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginationResult[AuditLog]:
        filters = [AuditLog.actor_id == actor_id]
        if actor_type:
            filters.append(AuditLog.actor_type == actor_type)

        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="timestamp",
            sort_order="desc",
        )

    async def get_logs_by_resource(
        self, db: AsyncSession, resource_id: str, page: int = 1, size: int = 50
    ) -> PaginationResult[AuditLog]:
        filters = [AuditLog.resource_id == resource_id]
        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="timestamp",
            sort_order="desc",
        )

    async def get_high_risk_events(
        self, db: AsyncSession, hours_back: int = 24, page: int = 1, size: int = 50
    ) -> PaginationResult[AuditLog]:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)

        filters = [
            AuditLog.timestamp >= cutoff,
            AuditLog.severity.in_([ActionSeverity.HIGH, ActionSeverity.CRITICAL]),
        ]

        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="timestamp",
            sort_order="desc",
        )

    async def search_compliance_events(
        self,
        db: AsyncSession,
        event_types: List[AuditEventType],
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        page: int = 1,
        size: int = 100,
    ) -> PaginationResult[AuditLog]:
        filters = [
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date,
            AuditLog.event_type.in_(event_types),
        ]

        return await self.get_paginated(
            db=db,
            page=page,
            size=size,
            filters=filters,
            sort_by="timestamp",
            sort_order="desc",
        )

    async def get_ai_execution_metrics(
        self, db: AsyncSession, days_back: int = 1
    ) -> Dict[str, Any]:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)

        query = (
            select(
                AuditLog.event_type,
                func.count(AuditLog.id).label("count"),
                func.sum(AuditLog.ai_prompt_tokens).label("total_prompt_tokens"),
                func.sum(AuditLog.ai_completion_tokens).label(
                    "total_completion_tokens"
                ),
            )
            .where(
                and_(
                    AuditLog.actor_type == ActorType.AI_AGENT,
                    AuditLog.timestamp >= cutoff,
                )
            )
            .group_by(AuditLog.event_type)
        )

        result = await db.execute(query)
        rows = result.all()

        metrics = {
            "time_window_days": days_back,
            "total_ai_actions": 0,
            "events_breakdown": {},
            "total_tokens_consumed": 0,
        }

        for row in rows:
            event_type = (
                row.event_type.value
                if hasattr(row.event_type, "value")
                else row.event_type
            )
            count = row.count
            p_tokens = row.total_prompt_tokens or 0
            c_tokens = row.total_completion_tokens or 0

            metrics["events_breakdown"][event_type] = count
            metrics["total_ai_actions"] += count
            metrics["total_tokens_consumed"] += p_tokens + c_tokens

        return metrics


audit_repository = AuditLogRepository()
