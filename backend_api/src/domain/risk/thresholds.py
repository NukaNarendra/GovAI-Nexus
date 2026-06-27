import math
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class EntityRiskCategory(str, Enum):
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    RESTRICTED = "RESTRICTED"


class JurisdictionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    PROHIBITED = "PROHIBITED"


class TransactionVelocityLimits(BaseModel):
    max_count_24h: int
    max_volume_24h: float
    max_count_7d: int
    max_volume_7d: float
    max_single_transaction: float


class ThresholdConfiguration(BaseModel):
    base_currency: str = "USD"
    absolute_hard_limit: float = 10000000.0
    auto_approval_limit: float = 50000.0
    hitl_mandatory_threshold: float = 250000.0
    velocity_limits: Dict[EntityRiskCategory, TransactionVelocityLimits]
    jurisdiction_multipliers: Dict[JurisdictionRiskLevel, float]
    ai_confidence_minimums: Dict[str, float]


class DynamicThresholdManager:
    def __init__(self):
        self._config = self._initialize_default_configuration()

    def _initialize_default_configuration(self) -> ThresholdConfiguration:
        velocity_matrix = {
            EntityRiskCategory.STANDARD: TransactionVelocityLimits(
                max_count_24h=50,
                max_volume_24h=500000.0,
                max_count_7d=250,
                max_volume_7d=2500000.0,
                max_single_transaction=100000.0,
            ),
            EntityRiskCategory.ELEVATED: TransactionVelocityLimits(
                max_count_24h=25,
                max_volume_24h=100000.0,
                max_count_7d=100,
                max_volume_7d=500000.0,
                max_single_transaction=25000.0,
            ),
            EntityRiskCategory.HIGH: TransactionVelocityLimits(
                max_count_24h=5,
                max_volume_24h=25000.0,
                max_count_7d=20,
                max_volume_7d=100000.0,
                max_single_transaction=10000.0,
            ),
            EntityRiskCategory.RESTRICTED: TransactionVelocityLimits(
                max_count_24h=0,
                max_volume_24h=0.0,
                max_count_7d=0,
                max_volume_7d=0.0,
                max_single_transaction=0.0,
            ),
        }

        jurisdiction_multipliers = {
            JurisdictionRiskLevel.LOW: 1.0,
            JurisdictionRiskLevel.MEDIUM: 0.5,
            JurisdictionRiskLevel.HIGH: 0.1,
            JurisdictionRiskLevel.PROHIBITED: 0.0,
        }

        ai_minimums = {
            "ACCOUNT_OPENING": 0.85,
            "WIRE_TRANSFER": 0.90,
            "COMPLIANCE_CLEARANCE": 0.95,
        }

        return ThresholdConfiguration(
            velocity_limits=velocity_matrix,
            jurisdiction_multipliers=jurisdiction_multipliers,
            ai_confidence_minimums=ai_minimums,
        )

    def get_current_configuration(self) -> ThresholdConfiguration:
        return self._config

    def update_configuration(self, new_config: ThresholdConfiguration) -> None:
        self._config = new_config

    def map_risk_score_to_category(self, risk_score: float) -> EntityRiskCategory:
        if risk_score >= 85.0:
            return EntityRiskCategory.RESTRICTED
        if risk_score >= 60.0:
            return EntityRiskCategory.HIGH
        if risk_score >= 25.0:
            return EntityRiskCategory.ELEVATED
        return EntityRiskCategory.STANDARD

    def calculate_dynamic_transaction_limit(
        self,
        entity_risk_score: float,
        jurisdiction_level: JurisdictionRiskLevel,
        historical_average_tx_amount: float,
        account_age_days: int,
    ) -> float:
        category = self.map_risk_score_to_category(entity_risk_score)

        if (
            category == EntityRiskCategory.RESTRICTED
            or jurisdiction_level == JurisdictionRiskLevel.PROHIBITED
        ):
            return 0.0

        base_limit = self._config.velocity_limits[category].max_single_transaction

        jurisdiction_multiplier = self._config.jurisdiction_multipliers[
            jurisdiction_level
        ]
        adjusted_limit = base_limit * jurisdiction_multiplier

        if historical_average_tx_amount > 0:
            behavioral_multiplier = min(
                historical_average_tx_amount * 3.0 / adjusted_limit, 2.0
            )
            adjusted_limit = adjusted_limit * max(behavioral_multiplier, 0.5)

        age_multiplier = 1.0
        if account_age_days < 30:
            age_multiplier = 0.25
        elif account_age_days < 90:
            age_multiplier = 0.50
        elif account_age_days > 365:
            age_multiplier = 1.25

        final_limit = adjusted_limit * age_multiplier

        return min(final_limit, self._config.absolute_hard_limit)

    def evaluate_velocity_breach(
        self,
        entity_risk_score: float,
        current_amount: float,
        count_24h: int,
        volume_24h: float,
        count_7d: int,
        volume_7d: float,
    ) -> tuple[bool, List[str]]:
        breaches = []
        category = self.map_risk_score_to_category(entity_risk_score)
        limits = self._config.velocity_limits[category]

        projected_count_24h = count_24h + 1
        projected_volume_24h = volume_24h + current_amount
        projected_count_7d = count_7d + 1
        projected_volume_7d = volume_7d + current_amount

        if projected_count_24h > limits.max_count_24h:
            breaches.append(
                f"24h transaction count ({projected_count_24h}) exceeds limit ({limits.max_count_24h})"
            )

        if projected_volume_24h > limits.max_volume_24h:
            breaches.append(
                f"24h transaction volume ({projected_volume_24h}) exceeds limit ({limits.max_volume_24h})"
            )

        if projected_count_7d > limits.max_count_7d:
            breaches.append(
                f"7d transaction count ({projected_count_7d}) exceeds limit ({limits.max_count_7d})"
            )

        if projected_volume_7d > limits.max_volume_7d:
            breaches.append(
                f"7d transaction volume ({projected_volume_7d}) exceeds limit ({limits.max_volume_7d})"
            )

        if current_amount > limits.max_single_transaction:
            breaches.append(
                f"Single transaction amount ({current_amount}) exceeds limit ({limits.max_single_transaction})"
            )

        return len(breaches) > 0, breaches

    def evaluate_statistical_anomaly(
        self, current_amount: float, historical_amounts: List[float]
    ) -> tuple[bool, float]:
        if not historical_amounts or len(historical_amounts) < 5:
            return False, 0.0

        mean = sum(historical_amounts) / len(historical_amounts)
        variance = sum((x - mean) ** 2 for x in historical_amounts) / len(
            historical_amounts
        )
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return current_amount > (mean * 2), (current_amount - mean)

        z_score = (current_amount - mean) / std_dev

        is_anomalous = z_score > 3.0
        return is_anomalous, z_score

    def requires_human_escalation(
        self,
        transaction_amount: float,
        dynamic_limit: float,
        ai_confidence: float,
        action_type: str,
        is_anomalous: bool,
    ) -> tuple[bool, str]:
        if transaction_amount >= self._config.hitl_mandatory_threshold:
            return (
                True,
                f"Amount {transaction_amount} exceeds absolute mandatory HITL threshold.",
            )

        if transaction_amount > dynamic_limit:
            return (
                True,
                f"Amount {transaction_amount} exceeds dynamic risk-adjusted limit {dynamic_limit}.",
            )

        required_confidence = self._config.ai_confidence_minimums.get(action_type, 0.95)
        if ai_confidence < required_confidence:
            return (
                True,
                f"AI confidence {ai_confidence} below required minimum {required_confidence} for {action_type}.",
            )

        if is_anomalous:
            return (
                True,
                "Statistical deviation (Z-Score > 3.0) detected against historical baseline.",
            )

        return False, "Within acceptable autonomous execution parameters."
