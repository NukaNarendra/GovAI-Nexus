from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum

class DataSourceType(str, Enum):
    CRM = "CRM"
    LEGACY_DB = "LEGACY_DB"
    OCR_DOCUMENT = "OCR_DOCUMENT"
    EXTERNAL_API = "EXTERNAL_API"

class PayloadType(str, Enum):
    KYC_PROFILE = "KYC_PROFILE"
    TRANSACTION = "TRANSACTION"
    AML_ALERT = "AML_ALERT"

class IngestionPayload(BaseModel):
    source_system: str = Field(..., description="The system originating the data")
    source_type: DataSourceType = Field(..., description="The type of the source system")
    payload_type: PayloadType = Field(..., description="The type of payload being ingested")
    raw_data: Dict[str, Any] = Field(..., description="The unstructured or semi-structured data payload")
    reference_id: str = Field(..., description="A unique identifier from the source system")

    @field_validator("raw_data")
    def validate_raw_data(cls, v):
        if not v:
            raise ValueError("raw_data cannot be empty")
        return v

class IngestionResponse(BaseModel):
    status: str
    message: str
    ingestion_id: str
    validated_schema: str
    requires_hitl: bool = False
