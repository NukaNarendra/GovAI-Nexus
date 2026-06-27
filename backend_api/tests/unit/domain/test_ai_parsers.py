import pytest
from pydantic import ValidationError
from src.domain.ai_agents.parsers import (
    KYCAnalysisSchema,
    TransactionAnalysisSchema,
    HITLLearningLoopSchema,
    UBOAssessment,
    IdentifiedRiskFactor,
    TransactionAnomalyAssessment,
    DiscrepancyAnalysis,
)
from src.domain.ai_agents.prompts import PromptBuilder


def test_kyc_schema_valid() -> None:
    data = {
        "entity_classification": "OPERATING_COMPANY",
        "ubo_assessment": {
            "identified_owners": ["Alice", "Bob"],
            "is_pep_suspected": False,
            "ownership_layers": 2,
            "obscurity_score": 0.2,
        },
        "risk_factors": [
            {
                "category": "JURISDICTION",
                "severity": "LOW",
                "description": "Standard cross-border",
                "relevant_data_points": ["source_country"],
            }
        ],
        "ai_confidence_score": 0.95,
        "recommended_action": "APPROVE",
        "primary_reasoning": "All documents clear.",
    }
    schema = KYCAnalysisSchema(**data)
    assert schema.recommended_action == "APPROVE"
    assert schema.ubo_assessment.ownership_layers == 2


def test_kyc_schema_invalid_action() -> None:
    data = {
        "entity_classification": "OPERATING_COMPANY",
        "ubo_assessment": {
            "identified_owners": [],
            "is_pep_suspected": False,
            "ownership_layers": 1,
            "obscurity_score": 0.1,
        },
        "risk_factors": [],
        "ai_confidence_score": 0.95,
        "recommended_action": "MAYBE",
        "primary_reasoning": "Not sure.",
    }
    with pytest.raises(ValidationError):
        KYCAnalysisSchema(**data)


def test_kyc_schema_invalid_confidence() -> None:
    data = {
        "entity_classification": "OPERATING_COMPANY",
        "ubo_assessment": {
            "identified_owners": [],
            "is_pep_suspected": False,
            "ownership_layers": 1,
            "obscurity_score": 0.1,
        },
        "risk_factors": [],
        "ai_confidence_score": 1.5,
        "recommended_action": "APPROVE",
        "primary_reasoning": "Clear.",
    }
    with pytest.raises(ValidationError):
        KYCAnalysisSchema(**data)


def test_transaction_schema_valid() -> None:
    data = {
        "anomaly_assessment": {
            "is_structuring_suspected": True,
            "is_velocity_abnormal": False,
            "is_purpose_logical": True,
            "jurisdiction_risk_level": "MEDIUM",
        },
        "risk_factors": [],
        "fatf_typology_matches": ["SMURFING"],
        "overall_risk_probability": 0.85,
        "ai_confidence_score": 0.90,
        "recommended_execution_status": "HOLD_FOR_REVIEW",
        "investigator_notes": "Structuring suspected based on 3 recent transfers.",
    }
    schema = TransactionAnalysisSchema(**data)
    assert schema.recommended_execution_status == "HOLD_FOR_REVIEW"
    assert schema.fatf_typology_matches == ["SMURFING"]


def test_transaction_schema_invalid_status() -> None:
    data = {
        "anomaly_assessment": {
            "is_structuring_suspected": False,
            "is_velocity_abnormal": False,
            "is_purpose_logical": True,
            "jurisdiction_risk_level": "LOW",
        },
        "risk_factors": [],
        "fatf_typology_matches": [],
        "overall_risk_probability": 0.1,
        "ai_confidence_score": 0.99,
        "recommended_execution_status": "JUST_DO_IT",
        "investigator_notes": "Clear.",
    }
    with pytest.raises(ValidationError):
        TransactionAnalysisSchema(**data)


def test_hitl_learning_schema_valid() -> None:
    data = {
        "ai_was_correct": False,
        "discrepancy_analysis": {
            "root_cause_category": "MISSING_CONTEXT",
            "human_insight_extracted": "Paper trail exists offline",
            "prompt_adjustment_recommendation": "Ask for paper trails",
        },
        "confidence_calibration_adjustment": -0.1,
    }
    schema = HITLLearningLoopSchema(**data)
    assert schema.ai_was_correct is False
    assert schema.discrepancy_analysis.root_cause_category == "MISSING_CONTEXT"


def test_prompt_builder_kyc() -> None:
    messages = PromptBuilder.build_kyc_prompt({"name": "Test"}, [{"history": 1}])
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Test" in messages[1]["content"]


def test_prompt_builder_transaction() -> None:
    messages = PromptBuilder.build_transaction_prompt(
        {"amt": 100}, {"src": 1}, {"dst": 2}
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "100" in messages[1]["content"]


def test_prompt_builder_hitl() -> None:
    messages = PromptBuilder.build_hitl_resolution_prompt(
        {"payload": 1}, {"decision": 2}, "notes", "action"
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "notes" in messages[1]["content"]
    assert "action" in messages[1]["content"]
