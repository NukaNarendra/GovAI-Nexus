import pytest
from src.domain.risk.calculator import EnterpriseRiskCalculator, RiskTier
from src.domain.compliance.aml_checks import AMLResult, AMLCheckStatus, AMLViolation


@pytest.fixture
def calc() -> EnterpriseRiskCalculator:
    return EnterpriseRiskCalculator()


def create_mock_aml_result(status: str, severity_list: list) -> AMLResult:
    violations = []
    for sev in severity_list:
        violations.append(
            AMLViolation(
                violation_code="MOCK_CODE",
                description="Mock description",
                severity=sev,
                matched_data={},
            )
        )
    return AMLResult(
        status=AMLCheckStatus(status),
        confidence_score=1.0,
        violations=violations,
        metadata={},
    )


def test_calculate_aml_risk_low(calc: EnterpriseRiskCalculator) -> None:
    res = create_mock_aml_result("CLEARED", [])
    score = calc._calculate_aml_risk(res)
    assert score == 0.0


def test_calculate_aml_risk_mixed(calc: EnterpriseRiskCalculator) -> None:
    res = create_mock_aml_result("FLAGGED_FOR_REVIEW", ["LOW", "MEDIUM"])
    score = calc._calculate_aml_risk(res)
    assert score == 40.0


def test_calculate_aml_risk_critical_capped(calc: EnterpriseRiskCalculator) -> None:
    res = create_mock_aml_result("BLOCKED_SANCTIONS", ["CRITICAL", "HIGH", "HIGH"])
    score = calc._calculate_aml_risk(res)
    assert score == 100.0


def test_calculate_jurisdiction_risk_high(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_jurisdiction_risk("USA", "IRN")
    assert score == 100.0
    score2 = calc._calculate_jurisdiction_risk("PRK", "CHN")
    assert score2 == 100.0


def test_calculate_jurisdiction_risk_medium(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_jurisdiction_risk("PAN", "USA")
    assert score == 65.0


def test_calculate_jurisdiction_risk_cross_border(
    calc: EnterpriseRiskCalculator,
) -> None:
    score = calc._calculate_jurisdiction_risk("USA", "CAN")
    assert score == 20.0


def test_calculate_jurisdiction_risk_domestic(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_jurisdiction_risk("USA", "USA")
    assert score == 0.0


def test_calculate_size_risk_no_history_small(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_size_risk(5000.0, 0.0)
    assert score == 10.0


def test_calculate_size_risk_no_history_large(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_size_risk(15000.0, 0.0)
    assert score == 40.0
    score2 = calc._calculate_size_risk(75000.0, 0.0)
    assert score2 == 75.0


def test_calculate_size_risk_extreme_deviation(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_size_risk(110000.0, 10000.0)
    assert score == 100.0


def test_calculate_size_risk_normal(calc: EnterpriseRiskCalculator) -> None:
    score = calc._calculate_size_risk(12000.0, 10000.0)
    assert score == 10.0


def test_calculate_account_age_risk_new(calc: EnterpriseRiskCalculator) -> None:
    import time

    now = time.time()
    score = calc._calculate_account_age_risk(now - 3600)
    assert score == 100.0


def test_calculate_account_age_risk_established(calc: EnterpriseRiskCalculator) -> None:
    import time

    now = time.time()
    score = calc._calculate_account_age_risk(now - (365 * 86400))
    assert score == 0.0


def test_comprehensive_risk_low_tier(calc: EnterpriseRiskCalculator) -> None:
    import time

    now = time.time()
    aml_res = create_mock_aml_result("CLEARED", [])
    assessment = calc.calculate_comprehensive_risk(
        aml_result=aml_res,
        transaction_amount=5000.0,
        source_country="USA",
        dest_country="USA",
        account_created_timestamp=now - (365 * 86400),
        entity_avg_amount=10000.0,
    )
    assert assessment.risk_tier == RiskTier.LOW_RISK
    assert assessment.requires_hitl is False
    assert assessment.requires_blocking is False


def test_comprehensive_risk_medium_tier(calc: EnterpriseRiskCalculator) -> None:
    import time

    now = time.time()
    aml_res = create_mock_aml_result("FLAGGED_FOR_REVIEW", ["LOW"])
    assessment = calc.calculate_comprehensive_risk(
        aml_result=aml_res,
        transaction_amount=15000.0,
        source_country="USA",
        dest_country="CAN",
        account_created_timestamp=now - (60 * 86400),
        entity_avg_amount=10000.0,
    )
    assert assessment.risk_tier == RiskTier.MEDIUM_RISK
    assert assessment.requires_hitl is True
    assert assessment.requires_blocking is False


def test_comprehensive_risk_unacceptable_due_to_sanctions(
    calc: EnterpriseRiskCalculator,
) -> None:
    import time

    now = time.time()
    aml_res = create_mock_aml_result("BLOCKED_SANCTIONS", ["CRITICAL"])
    assessment = calc.calculate_comprehensive_risk(
        aml_result=aml_res,
        transaction_amount=5000.0,
        source_country="USA",
        dest_country="USA",
        account_created_timestamp=now - (365 * 86400),
        entity_avg_amount=10000.0,
    )
    assert assessment.risk_tier == RiskTier.UNACCEPTABLE_RISK
    assert assessment.requires_hitl is True
    assert assessment.requires_blocking is True
    assert assessment.total_score >= 95.0
