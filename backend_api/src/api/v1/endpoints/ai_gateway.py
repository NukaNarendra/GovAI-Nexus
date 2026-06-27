import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.api.dependencies import get_db, get_llm_client, get_current_user
from src.infrastructure.llm_provider.groq_client import GroqClientManager
from src.infrastructure.database.models.user import User
from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    RiskCategory,
    PriorityLevel,
)
from src.infrastructure.database.repository.audit_repo import audit_repository

from src.domain.compliance.aml_checks import AntiMoneyLaunderingEngine
from src.domain.risk.calculator import EnterpriseRiskCalculator
from src.domain.compliance.rule_engine import ComplianceRuleEngine
from src.domain.ai_agents.orchestrator import AIAgentOrchestrator
from src.domain.audit.logger_service import AuditLoggerService
from src.domain.audit.worm_storage import WORMStorageManager

router = APIRouter()


class KYCOnboardingRequest(BaseModel):
    entity_payload: Dict[str, Any]
    historical_data: List[Dict[str, Any]] = []


class TransactionEvaluationRequest(BaseModel):
    transaction_payload: Dict[str, Any]
    source_profile: Dict[str, Any]
    destination_profile: Dict[str, Any]


class GatewayResponse(BaseModel):
    orchestration_id: str
    status: str
    requires_human_review: bool
    governance_verdict: Dict[str, Any]
    ai_confidence: float


def get_orchestrator(
    llm_client: GroqClientManager = Depends(get_llm_client),
) -> AIAgentOrchestrator:
    aml_engine = AntiMoneyLaunderingEngine()
    risk_calculator = EnterpriseRiskCalculator()
    rule_engine = ComplianceRuleEngine(aml_engine, risk_calculator)
    return AIAgentOrchestrator(llm_client, rule_engine)


def get_audit_logger() -> AuditLoggerService:
    worm_storage = WORMStorageManager(audit_repository)
    return AuditLoggerService(audit_repository, worm_storage)


async def _dispatch_to_hitl_queue(
    db: AsyncSession,
    orchestration_result: Dict[str, Any],
    resource_id: str,
    resource_type: str,
    risk_category: RiskCategory,
) -> str:
    queue_item = HITLQueue(
        risk_category=risk_category,
        priority=PriorityLevel.HIGH
        if orchestration_result["governance_decision"]["requires_hard_block"]
        else PriorityLevel.MEDIUM,
        agent_id="CORE_AGENT_V1",
        model_version=orchestration_result["ai_analysis"].get("model_used", "UNKNOWN"),
        ai_confidence_score=orchestration_result["ai_analysis"].get(
            "ai_confidence_score", 0.0
        ),
        resource_id=resource_id,
        resource_type=resource_type,
        transaction_context={
            "orchestration_id": orchestration_result["orchestration_id"]
        },
        compliance_flags=orchestration_result["governance_decision"],
        ai_reasoning=orchestration_result["ai_analysis"].get(
            "primary_reasoning",
            orchestration_result["ai_analysis"].get("investigator_notes", ""),
        ),
    )
    db.add(queue_item)
    await db.flush()
    return queue_item.id


@router.post("/kyc/onboard", response_model=GatewayResponse)
async def trigger_kyc_onboarding(
    request: KYCOnboardingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AIAgentOrchestrator = Depends(get_orchestrator),
    audit_logger: AuditLoggerService = Depends(get_audit_logger),
    current_user: User = Depends(get_current_user),
) -> Any:
    try:
        orchestration_result = await orchestrator.process_kyc_onboarding(
            entity_payload=request.entity_payload,
            historical_data=request.historical_data,
        )

        resource_id = request.entity_payload.get(
            "entity_id", f"UNKNOWN_{uuid.uuid4().hex[:8]}"
        )

        if orchestration_result["requires_human_review"]:
            await _dispatch_to_hitl_queue(
                db=db,
                orchestration_result=orchestration_result,
                resource_id=resource_id,
                resource_type="CORPORATE_ENTITY",
                risk_category=RiskCategory.KYC_ANOMALY,
            )

        log_record = await audit_logger.log_ai_execution(
            db=db,
            agent_id=orchestrator.agent_id,
            resource_id=resource_id,
            resource_type="CORPORATE_ENTITY",
            execution_directive=orchestration_result["final_onboarding_status"],
            payload=request.entity_payload,
            ai_analysis=orchestration_result["ai_analysis"],
            governance_verdict=orchestration_result["governance_decision"]["verdict"],
        )

        await db.commit()

        return GatewayResponse(
            orchestration_id=orchestration_result["orchestration_id"],
            status=orchestration_result["final_onboarding_status"],
            requires_human_review=orchestration_result["requires_human_review"],
            governance_verdict=orchestration_result["governance_decision"],
            ai_confidence=orchestration_result["ai_analysis"].get(
                "ai_confidence_score", 0.0
            ),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/transactions/evaluate", response_model=GatewayResponse)
async def trigger_transaction_evaluation(
    request: TransactionEvaluationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AIAgentOrchestrator = Depends(get_orchestrator),
    audit_logger: AuditLoggerService = Depends(get_audit_logger),
    current_user: User = Depends(get_current_user),
) -> Any:
    try:
        orchestration_result = await orchestrator.process_wire_transfer(
            transaction_payload=request.transaction_payload,
            source_profile=request.source_profile,
            destination_profile=request.destination_profile,
        )

        resource_id = request.transaction_payload.get(
            "transaction_id", f"UNKNOWN_{uuid.uuid4().hex[:8]}"
        )

        if orchestration_result["requires_human_review"]:
            await _dispatch_to_hitl_queue(
                db=db,
                orchestration_result=orchestration_result,
                resource_id=resource_id,
                resource_type="WIRE_TRANSFER",
                risk_category=RiskCategory.AML_FLAG,
            )

        log_record = await audit_logger.log_ai_execution(
            db=db,
            agent_id=orchestrator.agent_id,
            resource_id=resource_id,
            resource_type="WIRE_TRANSFER",
            execution_directive=orchestration_result["execution_directive"],
            payload=request.transaction_payload,
            ai_analysis=orchestration_result["ai_analysis"],
            governance_verdict=orchestration_result["governance_decision"]["verdict"],
        )

        await db.commit()

        return GatewayResponse(
            orchestration_id=orchestration_result["orchestration_id"],
            status=orchestration_result["execution_directive"],
            requires_human_review=orchestration_result["requires_human_review"],
            governance_verdict=orchestration_result["governance_decision"],
            ai_confidence=orchestration_result["ai_analysis"].get(
                "ai_confidence_score", 0.0
            ),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
