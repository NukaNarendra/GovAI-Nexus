import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.infrastructure.llm_provider.groq_client import (
    GroqClientManager,
    OutputParsingError,
)
from src.domain.ai_agents.prompts import PromptBuilder
from src.domain.ai_agents.parsers import (
    KYCAnalysisSchema,
    TransactionAnalysisSchema,
    HITLLearningLoopSchema,
)
from src.domain.compliance.rule_engine import (
    ComplianceRuleEngine,
    AIExecutionProposal,
    GovernanceDecision,
    GovernanceVerdict,
)

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    pass


class AIAgentOrchestrator:
    def __init__(
        self,
        llm_client: GroqClientManager,
        rule_engine: ComplianceRuleEngine,
        agent_id: str = "CORE_AGENT_V1",
    ):
        self.llm_client = llm_client
        self.rule_engine = rule_engine
        self.agent_id = agent_id

    async def _safe_llm_execution(
        self, messages: List[Dict[str, str]], schema: Any, fallback_action: str
    ) -> Tuple[Dict[str, Any], bool]:
        try:
            response = await self.llm_client.generate_json_structured_output(
                messages=messages, response_schema=schema, temperature=0.0
            )
            return response["parsed_data"], True
        except OutputParsingError as e:
            logger.error(f"LLM Output Parsing Failure: {str(e)}")
            fallback_payload = {
                "recommended_action": fallback_action,
                "recommended_execution_status": fallback_action,
                "ai_confidence_score": 0.0,
                "primary_reasoning": f"SYSTEM FAILURE: Output parsing error. Fallback to {fallback_action} triggered.",
                "investigator_notes": f"SYSTEM FAILURE: Output parsing error. Fallback to {fallback_action} triggered.",
                "risk_factors": [
                    {
                        "category": "SYSTEM_ERROR",
                        "severity": "CRITICAL",
                        "description": str(e),
                        "relevant_data_points": [],
                    }
                ],
            }
            if schema == KYCAnalysisSchema:
                fallback_payload.update(
                    {
                        "entity_classification": "UNKNOWN",
                        "ubo_assessment": {
                            "identified_owners": [],
                            "is_pep_suspected": True,
                            "ownership_layers": 99,
                            "obscurity_score": 1.0,
                        },
                    }
                )
            elif schema == TransactionAnalysisSchema:
                fallback_payload.update(
                    {
                        "anomaly_assessment": {
                            "is_structuring_suspected": True,
                            "is_velocity_abnormal": True,
                            "is_purpose_logical": False,
                            "jurisdiction_risk_level": "CRITICAL",
                        },
                        "fatf_typology_matches": ["SYSTEM_EVALUATION_FAILURE"],
                        "overall_risk_probability": 1.0,
                    }
                )
            return fallback_payload, False
        except Exception as e:
            logger.critical(f"Critical LLM Failure: {str(e)}")
            raise OrchestrationError(f"Failed to execute LLM workflow: {str(e)}")

    async def process_kyc_onboarding(
        self, entity_payload: Dict[str, Any], historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        messages = PromptBuilder.build_kyc_prompt(entity_payload, historical_data)

        parsed_output, is_valid = await self._safe_llm_execution(
            messages=messages, schema=KYCAnalysisSchema, fallback_action="ESCALATE"
        )

        proposal = AIExecutionProposal(
            agent_id=self.agent_id,
            target_resource_id=entity_payload.get("entity_id", "UNKNOWN"),
            action_type="ACCOUNT_OPENING",
            proposed_payload=entity_payload,
            ai_confidence=parsed_output.get("ai_confidence_score", 0.0),
            ai_reasoning=parsed_output.get("primary_reasoning", ""),
        )

        governance_decision = await self.rule_engine.evaluate_ai_proposal(proposal)

        final_status = "PENDING_HITL"
        if (
            governance_decision.verdict == GovernanceVerdict.APPROVED_AUTO
            and parsed_output.get("recommended_action") == "APPROVE"
        ):
            final_status = "APPROVED"
        elif (
            governance_decision.verdict == GovernanceVerdict.REJECTED_AUTO
            or parsed_output.get("recommended_action") == "REJECT"
        ):
            final_status = "REJECTED"

        return {
            "orchestration_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "final_onboarding_status": final_status,
            "ai_analysis": parsed_output,
            "governance_decision": governance_decision.model_dump(),
            "requires_human_review": final_status == "PENDING_HITL",
        }

    async def process_wire_transfer(
        self,
        transaction_payload: Dict[str, Any],
        source_profile: Dict[str, Any],
        destination_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        messages = PromptBuilder.build_transaction_prompt(
            transaction_payload, source_profile, destination_profile
        )

        parsed_output, is_valid = await self._safe_llm_execution(
            messages=messages,
            schema=TransactionAnalysisSchema,
            fallback_action="HOLD_FOR_REVIEW",
        )

        proposal = AIExecutionProposal(
            agent_id=self.agent_id,
            target_resource_id=transaction_payload.get("transaction_id", "UNKNOWN"),
            action_type="WIRE_TRANSFER",
            proposed_payload=transaction_payload,
            ai_confidence=parsed_output.get("ai_confidence_score", 0.0),
            ai_reasoning=parsed_output.get("investigator_notes", ""),
        )

        governance_decision = await self.rule_engine.evaluate_ai_proposal(proposal)

        final_execution_directive = "HOLD_FOR_REVIEW"

        if (
            governance_decision.requires_hard_block
            or parsed_output.get("recommended_execution_status") == "BLOCK"
        ):
            final_execution_directive = "BLOCK_TRANSACTION"
        elif (
            governance_decision.verdict == GovernanceVerdict.APPROVED_AUTO
            and parsed_output.get("recommended_execution_status") == "EXECUTE"
        ):
            final_execution_directive = "EXECUTE_TRANSACTION"

        return {
            "orchestration_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "execution_directive": final_execution_directive,
            "ai_analysis": parsed_output,
            "governance_decision": governance_decision.model_dump(),
            "requires_human_review": final_execution_directive == "HOLD_FOR_REVIEW",
        }

    async def generate_hitl_feedback_loop(
        self,
        original_payload: Dict[str, Any],
        ai_decision: Dict[str, Any],
        human_notes: str,
        human_action: str,
    ) -> Dict[str, Any]:
        messages = PromptBuilder.build_hitl_resolution_prompt(
            original_payload, ai_decision, human_notes, human_action
        )

        parsed_output, is_valid = await self._safe_llm_execution(
            messages=messages, schema=HITLLearningLoopSchema, fallback_action="ERROR"
        )

        return {
            "feedback_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "learning_extraction": parsed_output,
        }
