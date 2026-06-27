from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class IdentifiedRiskFactor(BaseModel):
    category: str = Field(
        ...,
        description="The category of the risk (e.g., JURISDICTION, VELOCITY, UBO_OBSCURITY)",
    )
    severity: str = Field(
        ..., description="Severity level: LOW, MEDIUM, HIGH, CRITICAL"
    )
    description: str = Field(
        ..., description="Detailed explanation of the specific risk factor identified"
    )
    relevant_data_points: List[str] = Field(
        ...,
        description="The exact keys or values from the input payload that triggered this risk",
    )


class UBOAssessment(BaseModel):
    identified_owners: List[str] = Field(
        ..., description="List of all ultimate beneficial owners identified in the text"
    )
    is_pep_suspected: bool = Field(
        ...,
        description="True if any owner matches Politically Exposed Person typologies",
    )
    ownership_layers: int = Field(
        ...,
        description="Number of corporate layers between the operating entity and the UBO",
    )
    obscurity_score: float = Field(
        ...,
        description="Score from 0.0 to 1.0 representing how difficult it is to trace ownership",
    )


class KYCAnalysisSchema(BaseModel):
    entity_classification: str = Field(
        ...,
        description="Classification: OPERATING_COMPANY, HOLDING_COMPANY, SHELL_COMPANY, TRUST",
    )
    ubo_assessment: UBOAssessment
    risk_factors: List[IdentifiedRiskFactor]
    ai_confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the analysis based on document clarity",
    )
    recommended_action: str = Field(
        ..., description="Must be exactly: APPROVE, REJECT, or ESCALATE"
    )
    primary_reasoning: str = Field(
        ...,
        description="A dense, highly technical explanation of the recommended action",
    )

    @field_validator("recommended_action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"APPROVE", "REJECT", "ESCALATE"}
        if v not in allowed:
            raise ValueError(f"recommended_action must be one of {allowed}")
        return v


class TransactionAnomalyAssessment(BaseModel):
    is_structuring_suspected: bool = Field(
        ..., description="True if transaction appears to avoid reporting thresholds"
    )
    is_velocity_abnormal: bool = Field(
        ..., description="True if transaction frequency/volume deviates from baseline"
    )
    is_purpose_logical: bool = Field(
        ..., description="True if transaction purpose aligns with entity NAICS/SIC code"
    )
    jurisdiction_risk_level: str = Field(
        ..., description="LOW, MEDIUM, HIGH, CRITICAL based on source/dest countries"
    )


class TransactionAnalysisSchema(BaseModel):
    anomaly_assessment: TransactionAnomalyAssessment
    risk_factors: List[IdentifiedRiskFactor]
    fatf_typology_matches: List[str] = Field(
        ..., description="List of recognized FATF red flags present in this transaction"
    )
    overall_risk_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Calculated probability of illicit activity"
    )
    ai_confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the analysis"
    )
    recommended_execution_status: str = Field(
        ..., description="Must be exactly: EXECUTE, BLOCK, or HOLD_FOR_REVIEW"
    )
    investigator_notes: str = Field(
        ..., description="Detailed audit trail reasoning for compliance records"
    )

    @field_validator("recommended_execution_status")
    @classmethod
    def validate_exec_status(cls, v: str) -> str:
        allowed = {"EXECUTE", "BLOCK", "HOLD_FOR_REVIEW"}
        if v not in allowed:
            raise ValueError(f"recommended_execution_status must be one of {allowed}")
        return v


class DiscrepancyAnalysis(BaseModel):
    root_cause_category: str = Field(
        ...,
        description="Category of AI failure: MISSING_CONTEXT, HALLUCINATION, OVERLY_STRICT, OVERLY_PERMISSIVE",
    )
    human_insight_extracted: str = Field(
        ...,
        description="The specific nuanced understanding the human applied that the AI missed",
    )
    prompt_adjustment_recommendation: str = Field(
        ...,
        description="Actionable recommendation to update SystemPrompts to prevent recurrence",
    )


class HITLLearningLoopSchema(BaseModel):
    ai_was_correct: bool = Field(
        ...,
        description="True if the human ultimately agreed with the AI's core assessment despite the override",
    )
    discrepancy_analysis: Optional[DiscrepancyAnalysis] = Field(
        None, description="Detailed analysis if the AI was incorrect"
    )
    confidence_calibration_adjustment: float = Field(
        ...,
        description="Suggested adjustment to confidence threshold based on this event (-0.1 to +0.1)",
    )
