import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from src.domain.compliance.aml_checks import (
    AntiMoneyLaunderingEngine,
    AMLResult,
    AMLCheckStatus,
)
from src.domain.risk.calculator import (
    EnterpriseRiskCalculator,
    RiskAssessment,
    RiskTier,
)


class GovernanceVerdict(str, Enum):
    APPROVED_AUTO = "APPROVED_AUTO"
    REJECTED_AUTO = "REJECTED_AUTO"
    ROUTED_TO_HITL = "ROUTED_TO_HITL"


class AIExecutionProposal(BaseModel):
    agent_id: str
    target_resource_id: str
    action_type: str
    proposed_payload: Dict[str, Any]
    ai_confidence: float
    ai_reasoning: str


class GovernanceDecision(BaseModel):
    decision_id: str
    timestamp: str
    verdict: GovernanceVerdict
    risk_assessment: RiskAssessment
    aml_results: AMLResult
    governance_notes: str
    requires_hard_block: bool


class ComplianceRuleEngine:
    def __init__(
        self,
        aml_engine: AntiMoneyLaunderingEngine,
        risk_calculator: EnterpriseRiskCalculator,
    ):
        self.aml_engine = aml_engine
        self.risk_calculator = risk_calculator

        self.strict_block_actions = {
            "WIRE_TRANSFER",
            "ACCOUNT_OPENING",
            "CREDIT_APPROVAL",
        }
        self.ai_confidence_threshold = 0.88

    async def _extract_transaction_context(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "entity_name": payload.get("entity_name", "UNKNOWN"),
            "beneficial_owners": payload.get("beneficial_owners", []),
            "source_account": payload.get("source_account_id", ""),
            "amount": float(payload.get("amount", 0.0)),
            "source_country": payload.get("source_country", "UNKNOWN"),
            "dest_country": payload.get("destination_country", "UNKNOWN"),
            "account_created_timestamp": payload.get(
                "account_created_timestamp", datetime.utcnow().timestamp()
            ),
            "entity_avg_amount": float(payload.get("historical_average_volume", 0.0)),
            "historical_transactions": payload.get("recent_transactions", []),
        }

    def _evaluate_ai_reliability(
        self, proposal: AIExecutionProposal
    ) -> Tuple[bool, str]:
        if proposal.ai_confidence < self.ai_confidence_threshold:
            return (
                False,
                f"AI confidence ({proposal.ai_confidence}) is below governance threshold ({self.ai_confidence_threshold})",
            )

        if len(proposal.ai_reasoning) < 20:
            return (
                False,
                "AI reasoning provided is too brief to satisfy audit requirements",
            )

        if (
            "sanction" in proposal.ai_reasoning.lower()
            and proposal.action_type in self.strict_block_actions
        ):
            return (
                False,
                "AI reasoning mentions sanctions but proposes execution. Semantic conflict detected.",
            )

        return True, "AI reliability checks passed"

    async def evaluate_ai_proposal(
        self, proposal: AIExecutionProposal
    ) -> GovernanceDecision:
        decision_id = f"GOV_{uuid.uuid4().hex[:12].upper()}"

        context = await self._extract_transaction_context(proposal.proposed_payload)

        aml_result = await self.aml_engine.run_full_aml_scan(
            entity_name=context["entity_name"],
            beneficial_owners=context["beneficial_owners"],
            source_account=context["source_account"],
            dest_country=context["dest_country"],
            source_country=context["source_country"],
            amount=context["amount"],
            historical_transactions=context["historical_transactions"],
        )

        risk_assessment = self.risk_calculator.calculate_comprehensive_risk(
            aml_result=aml_result,
            transaction_amount=context["amount"],
            source_country=context["source_country"],
            dest_country=context["dest_country"],
            account_created_timestamp=context["account_created_timestamp"],
            entity_avg_amount=context["entity_avg_amount"],
        )

        ai_reliable, ai_reliability_notes = self._evaluate_ai_reliability(proposal)

        verdict = GovernanceVerdict.APPROVED_AUTO
        notes = []
        requires_hard_block = False

        if risk_assessment.requires_blocking or aml_result.status in [
            AMLCheckStatus.BLOCKED_SANCTIONS,
            AMLCheckStatus.BLOCKED_STRUCTURING,
        ]:
            verdict = GovernanceVerdict.REJECTED_AUTO
            requires_hard_block = True
            notes.append(
                "HARD BLOCK: Critical compliance violation or unacceptable risk score."
            )

        elif risk_assessment.requires_hitl or not ai_reliable:
            verdict = GovernanceVerdict.ROUTED_TO_HITL
            notes.append(
                "HITL REQUIRED: Risk threshold exceeded or AI reliability validation failed."
            )
            if not ai_reliable:
                notes.append(f"AI Check Failure: {ai_reliability_notes}")

        else:
            notes.append(
                "APPROVED: AI proposal validated against enterprise compliance matrices. Risk within acceptable parameters."
            )

        return GovernanceDecision(
            decision_id=decision_id,
            timestamp=datetime.utcnow().isoformat(),
            verdict=verdict,
            risk_assessment=risk_assessment,
            aml_results=aml_result,
            governance_notes=" | ".join(notes),
            requires_hard_block=requires_hard_block,
        )
