import logging
import io
import csv
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from src.api.dependencies import get_current_user, get_db
from src.infrastructure.database.session import db_manager
from src.infrastructure.database.models.user import User
from src.infrastructure.database.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter()


class AIMetricsResponse(BaseModel):
    total_ai_actions: int
    events_breakdown: Dict[str, int]
    timestamp: str
    days_analyzed: int
    error_detected: Optional[str] = None


class AuditLogItem(BaseModel):
    id: str
    timestamp: Optional[str]
    event_type: str
    severity: str
    actor_id: str
    actor_type: str
    resource_id: Optional[str]
    action_details: str
    cryptographic_hash: str
    previous_hash: str
    is_tampered: bool


class AuditLogPaginatedResponse(BaseModel):
    items: List[AuditLogItem]
    page: int
    size: int
    total_returned: int


@router.get(
    "/ai-metrics", response_model=AIMetricsResponse, status_code=status.HTTP_200_OK
)
async def get_ai_metrics(
    days_back: int = Query(1, ge=1, le=90),
    db: AsyncSession = Depends(db_manager.get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        stmt = select(AuditLog).where(AuditLog.timestamp >= cutoff_date)
        result = await db.execute(stmt)
        logs = result.scalars().all()

        total_ai_actions = 0
        events_breakdown: Dict[str, int] = {
            "AI_DECISION_EXECUTED": 0,
            "AI_DECISION_REJECTED": 0,
            "RISK_THRESHOLD_EXCEEDED": 0,
            "COMPLIANCE_RULE_TRIGGERED": 0,
            "HITL_OVERRIDE": 0,
        }

        for log in logs:
            if getattr(log, "actor_type", "") == "AI_AGENT":
                total_ai_actions += 1
            event_type = getattr(log, "event_type", "UNKNOWN")
            if event_type in events_breakdown:
                events_breakdown[event_type] += 1
            else:
                events_breakdown[event_type] = 1

        return AIMetricsResponse(
            total_ai_actions=total_ai_actions,
            events_breakdown=events_breakdown,
            timestamp=datetime.utcnow().isoformat(),
            days_analyzed=days_back,
        )

    except Exception as e:
        logger.error(f"Failed to fetch AI metrics: {str(e)}")
        return AIMetricsResponse(
            total_ai_actions=0,
            events_breakdown={},
            timestamp=datetime.utcnow().isoformat(),
            days_analyzed=days_back,
            error_detected=str(e),
        )


@router.get(
    "/logs", response_model=AuditLogPaginatedResponse, status_code=status.HTTP_200_OK
)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if severity:
        stmt = stmt.where(AuditLog.severity == severity)

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    formatted_logs = []
    for log in logs:
        formatted_logs.append(
            AuditLogItem(
                id=log.id,
                timestamp=log.timestamp.isoformat() if log.timestamp else None,
                event_type=log.event_type,
                severity=log.severity,
                actor_id=log.actor_id,
                actor_type=log.actor_type,
                resource_id=log.resource_id,
                action_details=log.action_details,
                cryptographic_hash=log.cryptographic_hash,
                previous_hash=log.previous_hash,
                is_tampered=getattr(log, "is_tampered", False),
            )
        )

    return AuditLogPaginatedResponse(
        items=formatted_logs, page=page, size=size, total_returned=len(formatted_logs)
    )


@router.get(
    "/logs/{log_id}", response_model=AuditLogItem, status_code=status.HTTP_200_OK
)
async def get_audit_log_by_id(
    log_id: str,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AuditLog).where(AuditLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalars().first()

    if not log:
        raise HTTPException(
            status_code=404, detail="Cryptographic Audit record not found"
        )

    return AuditLogItem(
        id=log.id,
        timestamp=log.timestamp.isoformat() if log.timestamp else None,
        event_type=log.event_type,
        severity=log.severity,
        actor_id=log.actor_id,
        actor_type=log.actor_type,
        resource_id=log.resource_id,
        action_details=log.action_details,
        cryptographic_hash=log.cryptographic_hash,
        previous_hash=log.previous_hash,
        is_tampered=getattr(log, "is_tampered", False),
    )


@router.get("/export/csv", status_code=status.HTTP_200_OK)
async def export_audit_logs_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
    result = await db.execute(stmt)
    logs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write CSV Header
    writer.writerow([
        "Timestamp", "Event Type", "Severity", "Actor Type", 
        "Actor ID", "Resource ID", "Action Details", "Cryptographic Hash", "Previous Hash"
    ])
    
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat() if log.timestamp else "",
            log.event_type,
            log.severity,
            log.actor_type,
            log.actor_id,
            log.resource_id,
            log.action_details,
            log.cryptographic_hash,
            log.previous_hash
        ])
        
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=regulatory_audit_report.csv"}
    )
