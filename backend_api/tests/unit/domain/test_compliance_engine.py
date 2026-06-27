import pytest
from datetime import datetime
from typing import Dict, Any, List
from src.domain.compliance.aml_checks import (
    AntiMoneyLaunderingEngine,
    AMLCheckStatus,
    SanctionList,
)
from src.domain.risk.calculator import EnterpriseRiskCalculator
from src.domain.compliance.rule_engine import (
    ComplianceRuleEngine,
    AIExecutionProposal,
    GovernanceVerdict,
)


@pytest.fixture
def aml_engine() -> AntiMoneyLaunderingEngine:
    return AntiMoneyLaunderingEngine(fuzzy_match_threshold=0.85)


@pytest.fixture
def risk_calc() -> EnterpriseRiskCalculator:
    return EnterpriseRiskCalculator()


@pytest.fixture
def rule_engine(
    aml_engine: AntiMoneyLaunderingEngine, risk_calc: EnterpriseRiskCalculator
) -> ComplianceRuleEngine:
    return ComplianceRuleEngine(aml_engine=aml_engine, risk_calculator=risk_calc)


def test_levenshtein_distance_exact_match(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    dist = aml_engine._levenshtein_distance("globalcorp", "globalcorp")
    assert dist == 0
    sim = aml_engine._calculate_string_similarity("globalcorp", "globalcorp")
    assert sim == 1.0


def test_levenshtein_distance_partial_match(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    dist = aml_engine._levenshtein_distance("globalcorp", "g1obalcorp")
    assert dist == 1
    sim = aml_engine._calculate_string_similarity("globalcorp", "g1obalcorp")
    assert sim == 0.9


def test_levenshtein_distance_no_match(aml_engine: AntiMoneyLaunderingEngine) -> None:
    sim = aml_engine._calculate_string_similarity("abcdef", "uvwxyz")
    assert sim == 0.0


def test_evaluate_sanctions_risk_exact_entity_match(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_sanctions_risk(
        "GLOBAL_SHELL_CORP", ["John Doe"]
    )
    assert hit is True
    assert len(violations) == 1
    assert violations[0].violation_code == "SANCTIONS_MATCH_ENTITY"
    assert violations[0].severity == "CRITICAL"


def test_evaluate_sanctions_risk_fuzzy_entity_match(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_sanctions_risk(
        "G1obal Sh3ll Corp", ["Jane Doe"]
    )
    assert hit is True
    assert len(violations) == 1
    assert violations[0].matched_data["similarity_score"] >= 0.85


def test_evaluate_sanctions_risk_ubo_match(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_sanctions_risk(
        "Clean Tech Ltd", ["RESTRICTED_TRADING_LTD", "Safe Owner"]
    )
    assert hit is True
    assert len(violations) == 1
    assert violations[0].violation_code == "SANCTIONS_MATCH_OWNER"
    assert violations[0].matched_data["owner"] == "RESTRICTED_TRADING_LTD"


def test_evaluate_sanctions_risk_clean(aml_engine: AntiMoneyLaunderingEngine) -> None:
    hit, violations = aml_engine.evaluate_sanctions_risk(
        "Standard Operations Inc", ["Alice Smith", "Bob Jones"]
    )
    assert hit is False
    assert len(violations) == 0


def test_evaluate_structuring_risk_clean_no_history(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_structuring_risk(5000.0, [])
    assert hit is False
    assert len(violations) == 0


def test_evaluate_structuring_risk_detected(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    now = datetime.utcnow().timestamp()
    history = [
        {"amount": 9500.0, "timestamp": now - 86400},
        {"amount": 9800.0, "timestamp": now - 172800},
    ]
    hit, violations = aml_engine.evaluate_structuring_risk(9900.0, history)
    assert hit is True
    assert len(violations) == 1
    assert violations[0].violation_code == "STRUCTURING_DETECTED"
    assert violations[0].matched_data["count"] == 3
    assert violations[0].matched_data["total_amount"] == 29200.0


def test_evaluate_structuring_risk_ignored_low_amounts(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    now = datetime.utcnow().timestamp()
    history = [
        {"amount": 1500.0, "timestamp": now - 86400},
        {"amount": 2800.0, "timestamp": now - 172800},
    ]
    hit, violations = aml_engine.evaluate_structuring_risk(3900.0, history)
    assert hit is False
    assert len(violations) == 0


def test_evaluate_structuring_risk_ignored_outside_window(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    now = datetime.utcnow().timestamp()
    history = [
        {"amount": 9500.0, "timestamp": now - (10 * 86400)},
        {"amount": 9800.0, "timestamp": now - (15 * 86400)},
    ]
    hit, violations = aml_engine.evaluate_structuring_risk(9900.0, history)
    assert hit is False
    assert len(violations) == 0


def test_evaluate_velocity_risk_high_count(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    now = datetime.utcnow().timestamp()
    history = [
        {"amount": 100.0, "timestamp": now - 3600, "source_account": "ACC_1"}
        for _ in range(16)
    ]
    hit, violations = aml_engine.evaluate_velocity_risk("ACC_1", 100.0, history)
    assert hit is True
    assert any(v.violation_code == "HIGH_VELOCITY_COUNT" for v in violations)


def test_evaluate_velocity_risk_volume_spike(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    now = datetime.utcnow().timestamp()
    history = [
        {"amount": 1000.0, "timestamp": now - (i * 86400), "source_account": "ACC_2"}
        for i in range(1, 31)
    ]
    hit, violations = aml_engine.evaluate_velocity_risk("ACC_2", 150000.0, history)
    assert hit is True
    assert any(v.violation_code == "VOLUME_SPIKE_DETECTED" for v in violations)


def test_evaluate_jurisdictional_risk_high(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_jurisdictional_risk("USA", "IRN")
    assert hit is True
    assert len(violations) == 1
    assert violations[0].violation_code == "HIGH_RISK_JURISDICTION"


def test_evaluate_jurisdictional_risk_medium(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    hit, violations = aml_engine.evaluate_jurisdictional_risk("PAN", "GBR")
    assert hit is True
    assert len(violations) == 1
    assert violations[0].violation_code == "MEDIUM_RISK_JURISDICTION"


def test_run_full_aml_scan_clean(aml_engine: AntiMoneyLaunderingEngine) -> None:
    import asyncio

    result = asyncio.run(
        aml_engine.run_full_aml_scan(
            entity_name="Valid Corp",
            beneficial_owners=["John Smith"],
            source_account="ACC_CLEAN",
            dest_country="USA",
            source_country="CAN",
            amount=5000.0,
            historical_transactions=[],
        )
    )
    assert result.status == AMLCheckStatus.CLEARED
    assert len(result.violations) == 0
    assert result.confidence_score == 1.0


def test_run_full_aml_scan_blocked_sanctions(
    aml_engine: AntiMoneyLaunderingEngine,
) -> None:
    import asyncio

    result = asyncio.run(
        aml_engine.run_full_aml_scan(
            entity_name="GLOBAL_SHELL_CORP",
            beneficial_owners=["John Smith"],
            source_account="ACC_BAD",
            dest_country="USA",
            source_country="CAN",
            amount=5000.0,
            historical_transactions=[],
        )
    )
    assert result.status == AMLCheckStatus.BLOCKED_SANCTIONS
    assert len(result.violations) == 1
    assert result.confidence_score == 0.99


def test_rule_engine_auto_approval(rule_engine: ComplianceRuleEngine) -> None:
    import asyncio

    proposal = AIExecutionProposal(
        agent_id="AGENT_1",
        target_resource_id="TXN_1",
        action_type="WIRE_TRANSFER",
        proposed_payload={
            "entity_name": "Safe Co",
            "beneficial_owners": ["Alice"],
            "source_account_id": "ACC_1",
            "amount": 1000.0,
            "source_country": "USA",
            "destination_country": "CAN",
            "account_created_timestamp": datetime.utcnow().timestamp() - 31536000,
            "historical_average_volume": 5000.0,
            "recent_transactions": [],
        },
        ai_confidence=0.95,
        ai_reasoning="The transaction is completely routine and presents zero flags.",
    )
    decision = asyncio.run(rule_engine.evaluate_ai_proposal(proposal))
    assert decision.verdict == GovernanceVerdict.APPROVED_AUTO
    assert decision.requires_hard_block is False


def test_rule_engine_routes_to_hitl_due_to_low_confidence(
    rule_engine: ComplianceRuleEngine,
) -> None:
    import asyncio

    proposal = AIExecutionProposal(
        agent_id="AGENT_1",
        target_resource_id="TXN_2",
        action_type="WIRE_TRANSFER",
        proposed_payload={
            "entity_name": "Safe Co",
            "beneficial_owners": ["Alice"],
            "source_account_id": "ACC_1",
            "amount": 1000.0,
            "source_country": "USA",
            "destination_country": "CAN",
            "account_created_timestamp": datetime.utcnow().timestamp() - 31536000,
            "historical_average_volume": 5000.0,
            "recent_transactions": [],
        },
        ai_confidence=0.75,
        ai_reasoning="I am not entirely sure about this transaction.",
    )
    decision = asyncio.run(rule_engine.evaluate_ai_proposal(proposal))
    assert decision.verdict == GovernanceVerdict.ROUTED_TO_HITL
    assert "confidence" in decision.governance_notes.lower()


def test_rule_engine_hard_block_due_to_aml(rule_engine: ComplianceRuleEngine) -> None:
    import asyncio

    proposal = AIExecutionProposal(
        agent_id="AGENT_1",
        target_resource_id="TXN_3",
        action_type="WIRE_TRANSFER",
        proposed_payload={
            "entity_name": "GLOBAL_SHELL_CORP",
            "beneficial_owners": ["Alice"],
            "source_account_id": "ACC_1",
            "amount": 1000.0,
            "source_country": "USA",
            "destination_country": "IRN",
            "account_created_timestamp": datetime.utcnow().timestamp(),
            "historical_average_volume": 0.0,
            "recent_transactions": [],
        },
        ai_confidence=0.99,
        ai_reasoning="Proceeding with execution despite severe risks.",
    )
    decision = asyncio.run(rule_engine.evaluate_ai_proposal(proposal))
    assert decision.verdict == GovernanceVerdict.REJECTED_AUTO
    assert decision.requires_hard_block is True
