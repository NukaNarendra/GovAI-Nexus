import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
from pydantic import BaseModel, Field, validator


class KYCValidationError(Exception):
    pass


class DocumentVerificationError(KYCValidationError):
    pass


class DocumentType(str, Enum):
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    CERTIFICATE_OF_INCORPORATION = "CERTIFICATE_OF_INCORPORATION"
    ARTICLES_OF_ASSOCIATION = "ARTICLES_OF_ASSOCIATION"
    MEMORANDUM_OF_ASSOCIATION = "MEMORANDUM_OF_ASSOCIATION"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    TAX_CERTIFICATE = "TAX_CERTIFICATE"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    EXPIRED = "EXPIRED"
    FRAUD_SUSPECTED = "FRAUD_SUSPECTED"


class PEPLevel(str, Enum):
    NONE = "NONE"
    DOMESTIC = "DOMESTIC"
    INTERNATIONAL = "INTERNATIONAL"
    RCA = "RELATIVES_AND_CLOSE_ASSOCIATES"


class AdverseMediaSeverity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DocumentMetadata(BaseModel):
    document_id: str
    document_type: DocumentType
    issuing_country: str
    issue_date: str
    expiry_date: Optional[str] = None
    extracted_text: str
    mrz_data: Optional[str] = None
    has_hologram: bool = False
    is_tampered: bool = False
    resolution_dpi: int = 300


class UBOInfo(BaseModel):
    full_name: str
    nationality: str
    date_of_birth: str
    percentage_ownership: float = Field(..., ge=0.0, le=100.0)
    is_pep: bool = False
    residential_address_country: str


class CorporateStructureInfo(BaseModel):
    entity_name: str
    registration_number: str
    incorporation_country: str
    operating_countries: List[str]
    industry_code: str
    total_ownership_layers: int
    ubos: List[UBOInfo]
    is_publicly_traded: bool
    stock_ticker: Optional[str] = None


class KYCValidationResult(BaseModel):
    status: VerificationStatus
    risk_score: float = Field(..., ge=0.0, le=100.0)
    verification_failures: List[str]
    pep_detected: bool
    adverse_media_severity: AdverseMediaSeverity
    corporate_complexity_score: float
    requires_enhanced_due_diligence: bool


class KYCValidationEngine:
    def __init__(self, required_ubo_threshold: float = 25.0):
        self.required_ubo_threshold = required_ubo_threshold
        self.fatf_high_risk = {"IRN", "PRK", "MMR"}
        self.fatf_grey_list = {
            "BGR",
            "BFA",
            "CMR",
            "HRV",
            "COD",
            "HTI",
            "JAM",
            "KEN",
            "MLI",
            "MOZ",
            "NAM",
            "NGA",
            "PHL",
            "SEN",
            "ZAF",
            "SSD",
            "SYR",
            "TZA",
            "TUR",
            "UGA",
            "VNM",
            "YEM",
        }
        self.high_risk_industries = {
            "6021",
            "6022",
            "6081",
            "6082",
            "6199",
            "6211",
            "7995",
            "5932",
            "5094",
        }
        self.mrz_pattern = re.compile(r"^[A-Z0-9<]{44}\n[A-Z0-9<]{44}$")

    def _validate_date_format(self, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _is_document_expired(self, expiry_date_str: Optional[str]) -> bool:
        if not expiry_date_str:
            return False
        if not self._validate_date_format(expiry_date_str):
            raise DocumentVerificationError(
                "Invalid expiry date format. Expected YYYY-MM-DD."
            )
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        return datetime.utcnow() > expiry_date

    def verify_identity_document(
        self, doc: DocumentMetadata
    ) -> Tuple[VerificationStatus, List[str]]:
        failures = []

        if doc.resolution_dpi < 150:
            failures.append("Document image resolution too low for reliable OCR.")

        if doc.is_tampered:
            failures.append("Cryptographic or forensic tampering indicators detected.")
            return VerificationStatus.FRAUD_SUSPECTED, failures

        if self._is_document_expired(doc.expiry_date):
            failures.append("Document has expired.")
            return VerificationStatus.EXPIRED, failures

        if doc.document_type == DocumentType.PASSPORT:
            if not doc.mrz_data:
                failures.append("Passport missing Machine Readable Zone (MRZ) data.")
            elif len(doc.mrz_data) < 80:
                failures.append("Invalid MRZ data length.")

        if failures:
            return VerificationStatus.MANUAL_REVIEW_REQUIRED, failures

        return VerificationStatus.VERIFIED, []

    def evaluate_corporate_complexity(self, structure: CorporateStructureInfo) -> float:
        if structure.is_publicly_traded:
            return 10.0

        complexity_score = 0.0

        layer_penalty = min(structure.total_ownership_layers * 15.0, 60.0)
        complexity_score += layer_penalty

        if structure.incorporation_country in self.fatf_grey_list:
            complexity_score += 25.0
        elif structure.incorporation_country in self.fatf_high_risk:
            complexity_score += 50.0

        jurisdiction_mismatch = 0
        for ubo in structure.ubos:
            if ubo.residential_address_country != structure.incorporation_country:
                jurisdiction_mismatch += 1

        if jurisdiction_mismatch > 0:
            complexity_score += min(jurisdiction_mismatch * 10.0, 30.0)

        return min(complexity_score, 100.0)

    def validate_ubo_declarations(self, ubos: List[UBOInfo]) -> Tuple[bool, List[str]]:
        failures = []
        total_percentage = sum(ubo.percentage_ownership for ubo in ubos)

        if total_percentage > 100.0:
            failures.append(f"Total UBO ownership exceeds 100% ({total_percentage}%).")
            return False, failures

        for ubo in ubos:
            if not self._validate_date_format(ubo.date_of_birth):
                failures.append(f"Invalid DOB format for UBO {ubo.full_name}.")

            age = (
                datetime.utcnow() - datetime.strptime(ubo.date_of_birth, "%Y-%m-%d")
            ).days / 365.25
            if age < 18:
                failures.append(
                    f"UBO {ubo.full_name} is a minor ({age:.1f} years old)."
                )

        return len(failures) == 0, failures

    def assess_pep_and_adverse_media(
        self, names: List[str], nationalities: List[str]
    ) -> Tuple[PEPLevel, AdverseMediaSeverity]:
        pep_detected = PEPLevel.NONE
        adverse_media = AdverseMediaSeverity.NONE

        for name in names:
            normalized_name = name.lower()
            if "minister" in normalized_name or "senator" in normalized_name:
                pep_detected = PEPLevel.DOMESTIC
            if "general" in normalized_name or "president" in normalized_name:
                pep_detected = PEPLevel.INTERNATIONAL

            if "fraud" in normalized_name or "indictment" in normalized_name:
                adverse_media = AdverseMediaSeverity.HIGH

        return pep_detected, adverse_media

    def calculate_industry_risk(self, industry_code: str) -> float:
        if industry_code in self.high_risk_industries:
            return 85.0
        if industry_code.startswith("6"):
            return 60.0
        if industry_code.startswith("5"):
            return 40.0
        return 15.0

    async def execute_full_kyc_validation(
        self,
        corporate_structure: CorporateStructureInfo,
        provided_documents: List[DocumentMetadata],
    ) -> KYCValidationResult:
        all_failures = []
        overall_status = VerificationStatus.VERIFIED

        for doc in provided_documents:
            doc_status, doc_failures = self.verify_identity_document(doc)
            if doc_status != VerificationStatus.VERIFIED:
                overall_status = doc_status
                all_failures.extend(doc_failures)

        ubo_valid, ubo_failures = self.validate_ubo_declarations(
            corporate_structure.ubos
        )
        if not ubo_valid:
            overall_status = VerificationStatus.REJECTED
            all_failures.extend(ubo_failures)

        complexity = self.evaluate_corporate_complexity(corporate_structure)
        if complexity > 80.0:
            all_failures.append(
                f"Corporate structure complexity exceeds acceptable threshold ({complexity})."
            )

        names_to_screen = [corporate_structure.entity_name] + [
            ubo.full_name for ubo in corporate_structure.ubos
        ]
        nationalities = [corporate_structure.incorporation_country] + [
            ubo.nationality for ubo in corporate_structure.ubos
        ]

        pep_level, media_severity = self.assess_pep_and_adverse_media(
            names_to_screen, nationalities
        )

        industry_risk = self.calculate_industry_risk(corporate_structure.industry_code)

        base_risk = (complexity * 0.4) + (industry_risk * 0.3)

        if pep_level != PEPLevel.NONE:
            base_risk += 25.0
            all_failures.append(f"PEP identified: {pep_level.value}")

        if media_severity in [AdverseMediaSeverity.HIGH, AdverseMediaSeverity.CRITICAL]:
            base_risk += 40.0
            all_failures.append(f"Adverse media detected: {media_severity.value}")

        final_risk_score = min(100.0, base_risk)

        edd_required = False
        if final_risk_score > 60.0 or pep_level != PEPLevel.NONE or complexity > 50.0:
            edd_required = True
            if overall_status == VerificationStatus.VERIFIED:
                overall_status = VerificationStatus.MANUAL_REVIEW_REQUIRED

        if final_risk_score >= 90.0:
            overall_status = VerificationStatus.REJECTED
            all_failures.append(
                "Calculated risk score exceeds maximum enterprise tolerance."
            )

        return KYCValidationResult(
            status=overall_status,
            risk_score=final_risk_score,
            verification_failures=list(set(all_failures)),
            pep_detected=pep_level != PEPLevel.NONE,
            adverse_media_severity=media_severity,
            corporate_complexity_score=complexity,
            requires_enhanced_due_diligence=edd_required,
        )
