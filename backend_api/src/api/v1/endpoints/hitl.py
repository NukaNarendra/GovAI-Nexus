import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from src.api.dependencies import (
    get_db,
    get_current_compliance_officer,
    get_llm_client,
)
from src.infrastructure.database.models.user import User
from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    RiskCategory,
    PriorityLevel,
)
from src.infrastructure.database.repository.hitl_repo import (
    hitl_repository,
    TaskAlreadyClaimedError,
)
from src.infrastructure.database.repository.audit_repo import audit_repository
from src.domain.audit.logger_service import AuditLoggerService
from src.domain.audit.worm_storage import WORMStorageManager
from src.domain.ai_agents.orchestrator import AIAgentOrchestrator
from src.domain.compliance.rule_engine import ComplianceRuleEngine
from src.domain.compliance.aml_checks import AntiMoneyLaunderingEngine
from src.domain.risk.calculator import EnterpriseRiskCalculator

router = APIRouter()


class HITLResolutionRequest(BaseModel):
    resolution_status: str
    officer_notes: str
    action_taken: str
    generate_ai_feedback: bool = True


class HITLQueueItemResponse(BaseModel):
    id: str
    status: str
    risk_category: str
    priority: int
    resource_id: str
    resource_type: str
    ai_confidence_score: float
    created_at: str
    time_in_queue: float


def get_audit_logger() -> AuditLoggerService:
    return AuditLoggerService(audit_repository, WORMStorageManager(audit_repository))


def safe_json_load(data: Any) -> Dict:
    """Safely parses JSON strings stored by SQLite."""
    if isinstance(data, dict):
        return data
    if not data:
        return {}
    try:
        return json.loads(data)
    except Exception:
        return {"raw_data": str(data)}


@router.get("/tasks/pending", response_model=Dict[str, Any])
async def list_pending_tasks(
    page: int = 1,
    size: int = 50,
    risk_category: Optional[RiskCategory] = None,
    priority: Optional[PriorityLevel] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    try:
        pagination_result = await hitl_repository.get_pending_tasks(
            db=db, page=page, size=size, risk_category=risk_category, priority=priority
        )

        return {
            "items": [task.to_dict() for task in pagination_result.items],
            "total": pagination_result.total,
            "page": pagination_result.page,
            "pages": pagination_result.pages,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/tasks/my-assignments", response_model=Dict[str, Any])
async def list_my_assignments(
    include_resolved: bool = False,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    try:
        pagination_result = await hitl_repository.get_tasks_assigned_to_user(
            db=db,
            user_id=current_user.id,
            include_resolved=include_resolved,
            page=page,
            size=size,
        )

        return {
            "items": [task.to_dict() for task in pagination_result.items],
            "total": pagination_result.total,
            "page": pagination_result.page,
            "pages": pagination_result.pages,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 🚀 FIX: RESTORED THE MISSING ENDPOINT REQUIRED BY THE REVIEW MODAL!
@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task_details(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    stmt = select(HITLQueue).where(HITLQueue.id == task_id)
    result = await db.execute(stmt)
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "resource_id": task.resource_id,
        "resource_type": task.resource_type,
        "transaction_context": safe_json_load(task.transaction_context),
        "compliance_flags": safe_json_load(task.compliance_flags),
        "ai_reasoning": task.ai_reasoning,
        "ai_confidence_score": task.ai_confidence_score,
        "risk_category": getattr(task.risk_category, "value", str(task.risk_category)),
        "task_status": getattr(task.task_status, "value", str(task.task_status)),
    }


@router.post("/tasks/{task_id}/claim", response_model=HITLQueueItemResponse)
async def claim_task_for_review(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    try:
        task = await hitl_repository.claim_task_with_lock(
            db=db, task_id=task_id, user_id=current_user.id
        )
        await db.commit()
        return task.to_dict()
    except TaskAlreadyClaimedError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


from fastapi import BackgroundTasks

@router.post("/tasks/{task_id}/resolve", response_model=Dict[str, Any])
async def resolve_escalated_task(
    task_id: str,
    request: HITLResolutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(get_llm_client),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    try:
        if request.resolution_status not in ["APPROVED", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="resolution_status must be APPROVED or REJECTED",
            )

        target_status = (
            HITLTaskStatus.APPROVED
            if request.resolution_status == "APPROVED"
            else HITLTaskStatus.REJECTED
        )

        task = await hitl_repository.get_or_fail(db, task_id)

        # Store these locally to avoid ORM binding issues in the background task
        tx_context = task.transaction_context
        flags = task.compliance_flags

        def run_ai_feedback_loop():
            import asyncio
            async def run():
                orchestrator = AIAgentOrchestrator(
                    llm_client,
                    ComplianceRuleEngine(
                        AntiMoneyLaunderingEngine(), EnterpriseRiskCalculator()
                    ),
                )
                try:
                    await orchestrator.generate_hitl_feedback_loop(
                        original_payload=tx_context,
                        ai_decision=flags,
                        human_notes=request.officer_notes,
                        human_action=request.action_taken,
                    )
                except Exception as e:
                    pass
            asyncio.create_task(run())

        if request.generate_ai_feedback:
            background_tasks.add_task(run_ai_feedback_loop)

        resolved_task = await hitl_repository.resolve_task_and_audit(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            status=target_status,
            notes=request.officer_notes,
            action=request.action_taken,
        )

        await db.commit()
        return {
            "task_id": task_id,
            "status": "RESOLVED",
            "resolution": request.resolution_status,
            "feedback_loop_generated": request.generate_ai_feedback,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/metrics", response_model=Dict[str, Any])
async def get_queue_health_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    try:
        metrics = await hitl_repository.get_queue_metrics(db=db)
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
