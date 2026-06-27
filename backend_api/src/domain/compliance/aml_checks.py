import re
import math
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel


class AMLCheckStatus(str, Enum):
    CLEARED = "CLEARED"
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"
    BLOCKED_SANCTIONS = "BLOCKED_SANCTIONS"
    BLOCKED_STRUCTURING = "BLOCKED_STRUCTURING"


class SanctionList(str, Enum):
    OFAC = "OFAC"
    UN = "UN_CONSOLIDATED"
    EU = "EU_FINANCIAL_SANCTIONS"
    HMT = "UK_HMT"


class AMLViolation(BaseModel):
    violation_code: str
    description: str
    severity: str
    matched_data: Dict[str, Any]


class AMLResult(BaseModel):
    status: AMLCheckStatus
    confidence_score: float
    violations: List[AMLViolation]
    metadata: Dict[str, Any]


class AntiMoneyLaunderingEngine:
    def __init__(self, fuzzy_match_threshold: float = 0.85):
        self.fuzzy_match_threshold = fuzzy_match_threshold
        self._load_internal_watchlists()

    def _load_internal_watchlists(self) -> None:
        self.sanctioned_entities = {
            "GLOBAL_SHELL_CORP": {
                "lists": [SanctionList.OFAC, SanctionList.EU],
                "risk": "CRITICAL",
            },
            "RESTRICTED_TRADING_LTD": {"lists": [SanctionList.UN], "risk": "CRITICAL"},
            "DARK_MARKET_LOGISTICS": {
                "lists": [SanctionList.OFAC, SanctionList.HMT],
                "risk": "CRITICAL",
            },
        }
        self.high_risk_jurisdictions = {"IRN", "PRK", "SYR", "CUB", "MMR"}
        self.medium_risk_jurisdictions = {"PAN", "CYM", "BHS", "VGB"}

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _calculate_string_similarity(self, s1: str, s2: str) -> float:
        s1 = re.sub(r"[^a-z0-9]", "", s1.lower())
        s2 = re.sub(r"[^a-z0-9]", "", s2.lower())
        if not s1 or not s2:
            return 0.0
        max_len = max(len(s1), len(s2))
        distance = self._levenshtein_distance(s1, s2)
        return 1.0 - (distance / max_len)

    def evaluate_sanctions_risk(
        self, entity_name: str, beneficial_owners: List[str]
    ) -> Tuple[bool, List[AMLViolation]]:
        violations = []
        highest_match = 0.0

        normalized_target = entity_name.upper().strip()

        for sanctioned_name, details in self.sanctioned_entities.items():
            similarity = self._calculate_string_similarity(
                normalized_target, sanctioned_name
            )
            highest_match = max(highest_match, similarity)

            if similarity >= self.fuzzy_match_threshold:
                violations.append(
                    AMLViolation(
                        violation_code="SANCTIONS_MATCH_ENTITY",
                        description=f"Entity name matched sanctioned entity {sanctioned_name}",
                        severity=details["risk"],
                        matched_data={
                            "similarity_score": similarity,
                            "lists": [l.value for l in details["lists"]],
                        },
                    )
                )

        for owner in beneficial_owners:
            normalized_owner = owner.upper().strip()
            for sanctioned_name, details in self.sanctioned_entities.items():
                similarity = self._calculate_string_similarity(
                    normalized_owner, sanctioned_name
                )
                if similarity >= self.fuzzy_match_threshold:
                    violations.append(
                        AMLViolation(
                            violation_code="SANCTIONS_MATCH_OWNER",
                            description=f"Beneficial owner matched sanctioned entity {sanctioned_name}",
                            severity=details["risk"],
                            matched_data={
                                "owner": owner,
                                "similarity_score": similarity,
                            },
                        )
                    )

        return len(violations) > 0, violations

    def evaluate_structuring_risk(
        self,
        amount: float,
        historical_transactions: List[Dict[str, Any]],
        window_days: int = 7,
    ) -> Tuple[bool, List[AMLViolation]]:
        violations = []
        reporting_threshold = 10000.0
        structuring_threshold_lower = 8500.0
        structuring_threshold_upper = 9999.99

        if structuring_threshold_lower <= amount <= structuring_threshold_upper:
            cutoff_date = datetime.utcnow().timestamp() - (window_days * 86400)
            recent_txns = [
                tx
                for tx in historical_transactions
                if tx.get("timestamp", 0) >= cutoff_date
            ]

            structuring_pattern_txns = [
                tx
                for tx in recent_txns
                if structuring_threshold_lower
                <= tx.get("amount", 0)
                <= structuring_threshold_upper
            ]

            if len(structuring_pattern_txns) >= 2:
                total_structured_amount = (
                    sum([tx.get("amount", 0) for tx in structuring_pattern_txns])
                    + amount
                )
                if total_structured_amount > reporting_threshold:
                    violations.append(
                        AMLViolation(
                            violation_code="STRUCTURING_DETECTED",
                            description=f"Multiple transactions just below reporting threshold within {window_days} days",
                            severity="HIGH",
                            matched_data={
                                "count": len(structuring_pattern_txns) + 1,
                                "total_amount": total_structured_amount,
                            },
                        )
                    )

        return len(violations) > 0, violations

    def evaluate_velocity_risk(
        self,
        source_account: str,
        amount: float,
        historical_transactions: List[Dict[str, Any]],
    ) -> Tuple[bool, List[AMLViolation]]:
        violations = []
        cutoff_24h = datetime.utcnow().timestamp() - 86400

        recent_txns = [
            tx
            for tx in historical_transactions
            if tx.get("timestamp", 0) >= cutoff_24h
            and tx.get("source_account") == source_account
        ]

        if len(recent_txns) > 15:
            violations.append(
                AMLViolation(
                    violation_code="HIGH_VELOCITY_COUNT",
                    description="Excessive number of outbound transactions in 24 hours",
                    severity="MEDIUM",
                    matched_data={"count": len(recent_txns)},
                )
            )

        total_24h_volume = sum([tx.get("amount", 0) for tx in recent_txns]) + amount

        avg_monthly_volume = self._calculate_historical_average(historical_transactions)

        if avg_monthly_volume > 0 and total_24h_volume > (avg_monthly_volume * 3):
            violations.append(
                AMLViolation(
                    violation_code="VOLUME_SPIKE_DETECTED",
                    description="24-hour transaction volume exceeds 300% of historical monthly average",
                    severity="HIGH",
                    matched_data={
                        "24h_volume": total_24h_volume,
                        "historical_avg": avg_monthly_volume,
                    },
                )
            )

        return len(violations) > 0, violations

    def _calculate_historical_average(
        self, historical_transactions: List[Dict[str, Any]]
    ) -> float:
        if not historical_transactions:
            return 0.0
        total_volume = sum(tx.get("amount", 0) for tx in historical_transactions)
        oldest_tx = min(
            historical_transactions, key=lambda x: x.get("timestamp", float("inf"))
        ).get("timestamp", 0)
        days_active = max(1, (datetime.utcnow().timestamp() - oldest_tx) / 86400)
        return (total_volume / days_active) * 30

    def evaluate_jurisdictional_risk(
        self, source_country: str, dest_country: str
    ) -> Tuple[bool, List[AMLViolation]]:
        violations = []

        if (
            source_country in self.high_risk_jurisdictions
            or dest_country in self.high_risk_jurisdictions
        ):
            violations.append(
                AMLViolation(
                    violation_code="HIGH_RISK_JURISDICTION",
                    description="Transaction involves FATF blacklisted or highly sanctioned jurisdiction",
                    severity="CRITICAL",
                    matched_data={
                        "source": source_country,
                        "destination": dest_country,
                    },
                )
            )
        elif (
            source_country in self.medium_risk_jurisdictions
            or dest_country in self.medium_risk_jurisdictions
        ):
            violations.append(
                AMLViolation(
                    violation_code="MEDIUM_RISK_JURISDICTION",
                    description="Transaction involves offshore financial center or grey-listed jurisdiction",
                    severity="MEDIUM",
                    matched_data={
                        "source": source_country,
                        "destination": dest_country,
                    },
                )
            )

        return len(violations) > 0, violations

    async def run_full_aml_scan(
        self,
        entity_name: str,
        beneficial_owners: List[str],
        source_account: str,
        dest_country: str,
        source_country: str,
        amount: float,
        historical_transactions: List[Dict[str, Any]],
    ) -> AMLResult:
        all_violations = []

        sanc_hit, sanc_vios = self.evaluate_sanctions_risk(
            entity_name, beneficial_owners
        )
        all_violations.extend(sanc_vios)

        struct_hit, struct_vios = self.evaluate_structuring_risk(
            amount, historical_transactions
        )
        all_violations.extend(struct_vios)

        vel_hit, vel_vios = self.evaluate_velocity_risk(
            source_account, amount, historical_transactions
        )
        all_violations.extend(vel_vios)

        jur_hit, jur_vios = self.evaluate_jurisdictional_risk(
            source_country, dest_country
        )
        all_violations.extend(jur_vios)

        status = AMLCheckStatus.CLEARED
        confidence = 1.0

        if any(v.severity == "CRITICAL" for v in all_violations):
            status = AMLCheckStatus.BLOCKED_SANCTIONS
            confidence = 0.99
        elif any(v.violation_code == "STRUCTURING_DETECTED" for v in all_violations):
            status = AMLCheckStatus.BLOCKED_STRUCTURING
            confidence = 0.95
        elif len(all_violations) > 0:
            status = AMLCheckStatus.FLAGGED_FOR_REVIEW
            confidence = 0.80

        return AMLResult(
            status=status,
            confidence_score=confidence,
            violations=all_violations,
            metadata={
                "scan_timestamp": datetime.utcnow().isoformat(),
                "total_checks_run": 4,
            },
        )
