import pytest
from datetime import datetime, timedelta
from src.domain.compliance.kyc_validators import (
    KYCValidationEngine,
    DocumentMetadata,
    DocumentType,
    VerificationStatus,
    UBOInfo,
    CorporateStructureInfo,
    PEPLevel,
    AdverseMediaSeverity,
    DocumentVerificationError,
)


@pytest.fixture
def kyc_engine() -> KYCValidationEngine:
    return KYCValidationEngine()


def test_document_expiry_valid(kyc_engine: KYCValidationEngine) -> None:
    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    doc = DocumentMetadata(
        document_id="DOC_1",
        document_type=DocumentType.PASSPORT,
        issuing_country="USA",
        issue_date="2020-01-01",
        expiry_date=future_date,
        extracted_text="John Doe",
        mrz_data="P<USAJOHN<<DOE<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n1234567890USA1234567M1234567<<<<<<<<<<<<<<00",
        resolution_dpi=300,
    )
    status, failures = kyc_engine.verify_identity_document(doc)
    assert status == VerificationStatus.VERIFIED
    assert len(failures) == 0


def test_document_expiry_invalid_format(kyc_engine: KYCValidationEngine) -> None:
    doc = DocumentMetadata(
        document_id="DOC_2",
        document_type=DocumentType.PASSPORT,
        issuing_country="USA",
        issue_date="2020-01-01",
        expiry_date="01/01/2025",
        extracted_text="John Doe",
        resolution_dpi=300,
    )
    with pytest.raises(DocumentVerificationError):
        kyc_engine.verify_identity_document(doc)


def test_document_expired(kyc_engine: KYCValidationEngine) -> None:
    past_date = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
    doc = DocumentMetadata(
        document_id="DOC_3",
        document_type=DocumentType.PASSPORT,
        issuing_country="USA",
        issue_date="2010-01-01",
        expiry_date=past_date,
        extracted_text="John Doe",
        resolution_dpi=300,
    )
    status, failures = kyc_engine.verify_identity_document(doc)
    assert status == VerificationStatus.EXPIRED
    assert len(failures) == 1


def test_document_resolution_failure(kyc_engine: KYCValidationEngine) -> None:
    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    doc = DocumentMetadata(
        document_id="DOC_4",
        document_type=DocumentType.NATIONAL_ID,
        issuing_country="GBR",
        issue_date="2020-01-01",
        expiry_date=future_date,
        extracted_text="Jane Smith",
        resolution_dpi=72,
    )
    status, failures = kyc_engine.verify_identity_document(doc)
    assert status == VerificationStatus.MANUAL_REVIEW_REQUIRED
    assert len(failures) == 1


def test_document_tampering_failure(kyc_engine: KYCValidationEngine) -> None:
    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    doc = DocumentMetadata(
        document_id="DOC_5",
        document_type=DocumentType.DRIVERS_LICENSE,
        issuing_country="CAN",
        issue_date="2020-01-01",
        expiry_date=future_date,
        extracted_text="Tampered Doc",
        is_tampered=True,
        resolution_dpi=300,
    )
    status, failures = kyc_engine.verify_identity_document(doc)
    assert status == VerificationStatus.FRAUD_SUSPECTED


def test_passport_mrz_validation_missing(kyc_engine: KYCValidationEngine) -> None:
    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    doc = DocumentMetadata(
        document_id="DOC_6",
        document_type=DocumentType.PASSPORT,
        issuing_country="USA",
        issue_date="2020-01-01",
        expiry_date=future_date,
        extracted_text="No MRZ",
        resolution_dpi=300,
    )
    status, failures = kyc_engine.verify_identity_document(doc)
    assert status == VerificationStatus.MANUAL_REVIEW_REQUIRED


def test_ubo_validation_total_exceeds_100(kyc_engine: KYCValidationEngine) -> None:
    ubos = [
        UBOInfo(
            full_name="Owner 1",
            nationality="USA",
            date_of_birth="1980-01-01",
            percentage_ownership=60.0,
            residential_address_country="USA",
        ),
        UBOInfo(
            full_name="Owner 2",
            nationality="USA",
            date_of_birth="1985-01-01",
            percentage_ownership=50.0,
            residential_address_country="USA",
        ),
    ]
    valid, failures = kyc_engine.validate_ubo_declarations(ubos)
    assert valid is False
    assert len(failures) == 1


def test_ubo_validation_minor_detected(kyc_engine: KYCValidationEngine) -> None:
    recent_date = (datetime.utcnow() - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    ubos = [
        UBOInfo(
            full_name="Minor Owner",
            nationality="USA",
            date_of_birth=recent_date,
            percentage_ownership=100.0,
            residential_address_country="USA",
        )
    ]
    valid, failures = kyc_engine.validate_ubo_declarations(ubos)
    assert valid is False
    assert len(failures) == 1


def test_corporate_complexity_public(kyc_engine: KYCValidationEngine) -> None:
    structure = CorporateStructureInfo(
        entity_name="Public Corp",
        registration_number="123",
        incorporation_country="USA",
        operating_countries=["USA"],
        industry_code="1234",
        total_ownership_layers=5,
        ubos=[],
        is_publicly_traded=True,
    )
    score = kyc_engine.evaluate_corporate_complexity(structure)
    assert score == 10.0


def test_corporate_complexity_layers_and_mismatch(
    kyc_engine: KYCValidationEngine,
) -> None:
    ubos = [
        UBOInfo(
            full_name="Owner",
            nationality="CAN",
            date_of_birth="1980-01-01",
            percentage_ownership=100.0,
            residential_address_country="CAN",
        )
    ]
    structure = CorporateStructureInfo(
        entity_name="Complex Corp",
        registration_number="123",
        incorporation_country="CYM",
        operating_countries=["CYM"],
        industry_code="1234",
        total_ownership_layers=3,
        ubos=ubos,
        is_publicly_traded=False,
    )
    score = kyc_engine.evaluate_corporate_complexity(structure)
    assert score == 45.0 + 10.0


def test_pep_screening_domestic(kyc_engine: KYCValidationEngine) -> None:
    pep, media = kyc_engine.assess_pep_and_adverse_media(["Minister John Doe"], ["USA"])
    assert pep == PEPLevel.DOMESTIC
    assert media == AdverseMediaSeverity.NONE


def test_pep_screening_international_and_adverse_media(
    kyc_engine: KYCValidationEngine,
) -> None:
    pep, media = kyc_engine.assess_pep_and_adverse_media(
        ["General Dictator", "Fraud indictment pending"], ["IRN"]
    )
    assert pep == PEPLevel.INTERNATIONAL
    assert media == AdverseMediaSeverity.HIGH


def test_industry_risk_scoring(kyc_engine: KYCValidationEngine) -> None:
    assert kyc_engine.calculate_industry_risk("6021") == 85.0
    assert kyc_engine.calculate_industry_risk("6123") == 60.0
    assert kyc_engine.calculate_industry_risk("5999") == 40.0
    assert kyc_engine.calculate_industry_risk("1234") == 15.0


def test_full_kyc_validation_success(kyc_engine: KYCValidationEngine) -> None:
    import asyncio

    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    docs = [
        DocumentMetadata(
            document_id="1",
            document_type=DocumentType.PASSPORT,
            issuing_country="USA",
            issue_date="2020-01-01",
            expiry_date=future_date,
            extracted_text="John Doe",
            mrz_data="P<USAJOHN<<DOE<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n1234567890USA1234567M1234567<<<<<<<<<<<<<<00",
            resolution_dpi=300,
        )
    ]
    ubos = [
        UBOInfo(
            full_name="John Doe",
            nationality="USA",
            date_of_birth="1980-01-01",
            percentage_ownership=100.0,
            residential_address_country="USA",
        )
    ]
    structure = CorporateStructureInfo(
        entity_name="Clean LLC",
        registration_number="123",
        incorporation_country="USA",
        operating_countries=["USA"],
        industry_code="1234",
        total_ownership_layers=1,
        ubos=ubos,
        is_publicly_traded=False,
    )

    result = asyncio.run(kyc_engine.execute_full_kyc_validation(structure, docs))
    assert result.status == VerificationStatus.VERIFIED
    assert result.requires_enhanced_due_diligence is False
    assert len(result.verification_failures) == 0


def test_full_kyc_validation_rejected_due_to_pep_and_media(
    kyc_engine: KYCValidationEngine,
) -> None:
    import asyncio

    future_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
    docs = [
        DocumentMetadata(
            document_id="1",
            document_type=DocumentType.PASSPORT,
            issuing_country="USA",
            issue_date="2020-01-01",
            expiry_date=future_date,
            extracted_text="General Fraud",
            mrz_data="P<USAGENERAL<<FRAUD<<<<<<<<<<<<<<<<<<<<<<<<<<\n1234567890USA1234567M1234567<<<<<<<<<<<<<<00",
            resolution_dpi=300,
        )
    ]
    ubos = [
        UBOInfo(
            full_name="General Fraud",
            nationality="PRK",
            date_of_birth="1960-01-01",
            percentage_ownership=100.0,
            residential_address_country="PRK",
        )
    ]
    structure = CorporateStructureInfo(
        entity_name="Shell Indictment Corp",
        registration_number="123",
        incorporation_country="PRK",
        operating_countries=["PRK"],
        industry_code="6021",
        total_ownership_layers=5,
        ubos=ubos,
        is_publicly_traded=False,
    )

    result = asyncio.run(kyc_engine.execute_full_kyc_validation(structure, docs))
    assert result.status == VerificationStatus.REJECTED
    assert result.requires_enhanced_due_diligence is True
    assert result.pep_detected is True
