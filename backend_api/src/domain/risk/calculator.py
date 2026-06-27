import math
from typing import Dict, Any, List
from enum import Enum
from pydantic import BaseModel
from src.domain.compliance.aml_checks import AMLResult


class RiskTier(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    UNACCEPTABLE_RISK = "UNACCEPTABLE_RISK"


class RiskAssessment(BaseModel):
    total_score: float
    risk_tier: RiskTier
    contributing_factors: Dict[str, float]
    requires_hitl: bool
    requires_blocking: bool


class EnterpriseRiskCalculator:
    def __init__(self):
        self.base_score = 0.0
        self.max_score = 100.0

        self.weights = {
            "aml_violations": 0.45,
            "jurisdiction": 0.25,
            "transaction_size": 0.15,
            "account_age": 0.10,
            "velocity": 0.05,
        }

        self.thresholds = {
            RiskTier.LOW_RISK: 25.0,
            RiskTier.MEDIUM_RISK: 60.0,
            RiskTier.HIGH_RISK: 85.0,
        }

    def _calculate_aml_risk(self, aml_result: AMLResult) -> float:
        score = 0.0
        severity_multipliers = {
            "LOW": 10.0,
            "MEDIUM": 30.0,
            "HIGH": 75.0,
            "CRITICAL": 100.0,
        }

        for violation in aml_result.violations:
            score += severity_multipliers.get(violation.severity, 0.0)

        return min(100.0, score)

    def _calculate_jurisdiction_risk(
        self, source_country: str, dest_country: str
    ) -> float:
        score = 0.0
        high_risk = {"IRN", "PRK", "SYR", "CUB", "MMR", "VEN", "RUS"}
        medium_risk = {"PAN", "CYM", "BHS", "VGB", "ARE", "MLT"}

        if source_country in high_risk or dest_country in high_risk:
            score = 100.0
        elif source_country in medium_risk or dest_country in medium_risk:
            score = 65.0
        elif source_country != dest_country:
            score = 20.0

        return score

    def _calculate_size_risk(self, amount: float, entity_avg_amount: float) -> float:
        if amount <= 0:
            return 0.0

        if entity_avg_amount <= 0:
            if amount > 50000:
                return 75.0
            if amount > 10000:
                return 40.0
            return 10.0

        deviation_ratio = amount / entity_avg_amount

        if deviation_ratio > 10.0:
            return 100.0
        if deviation_ratio > 5.0:
            return 80.0
        if deviation_ratio > 2.0:
            return 50.0

        return 10.0

    def _calculate_account_age_risk(self, account_created_timestamp: float) -> float:
        import time

        days_old = (time.time() - account_created_timestamp) / 86400

        if days_old < 1:
            return 100.0
        if days_old < 7:
            return 80.0
        if days_old < 30:
            return 50.0
        if days_old < 90:
            return 20.0

        return 0.0

    def calculate_comprehensive_risk(
        self,
        aml_result: AMLResult,
        transaction_amount: float,
        source_country: str,
        dest_country: str,
        account_created_timestamp: float,
        entity_avg_amount: float,
    ) -> RiskAssessment:
        factors = {}

        factors["aml_violations"] = self._calculate_aml_risk(aml_result)
        factors["jurisdiction"] = self._calculate_jurisdiction_risk(
            source_country, dest_country
        )
        factors["transaction_size"] = self._calculate_size_risk(
            transaction_amount, entity_avg_amount
        )
        factors["account_age"] = self._calculate_account_age_risk(
            account_created_timestamp
        )

        total_weighted_score = 0.0
        for key, raw_score in factors.items():
            total_weighted_score += raw_score * self.weights.get(key, 0.0)

        final_score = round(
            min(self.max_score, max(self.base_score, total_weighted_score)), 2
        )

        if aml_result.status in [
            "BLOCKED_SANCTIONS",
            "BLOCKED_STRUCTURING",
        ] or "CRITICAL" in [v.severity for v in aml_result.violations]:
            final_score = max(final_score, 95.0)

        if final_score <= self.thresholds[RiskTier.LOW_RISK]:
            tier = RiskTier.LOW_RISK
            requires_hitl = False
            requires_blocking = False
        elif final_score <= self.thresholds[RiskTier.MEDIUM_RISK]:
            tier = RiskTier.MEDIUM_RISK
            requires_hitl = True
            requires_blocking = False
        elif final_score <= self.thresholds[RiskTier.HIGH_RISK]:
            tier = RiskTier.HIGH_RISK
            requires_hitl = True
            requires_blocking = False
        else:
            tier = RiskTier.UNACCEPTABLE_RISK
            requires_hitl = True
            requires_blocking = True

        return RiskAssessment(
            total_score=final_score,
            risk_tier=tier,
            contributing_factors=factors,
            requires_hitl=requires_hitl,
            requires_blocking=requires_blocking,
        )
