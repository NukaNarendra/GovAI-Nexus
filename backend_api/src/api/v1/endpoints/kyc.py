from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_user

router = APIRouter()

@router.get("/profiles", response_model=Dict[str, Any])
async def get_kyc_profiles(
    current_user = Depends(get_current_user)
) -> Any:
    """
    Get a simulated list of enterprise KYC profiles.
    In a real implementation, this would query the Data Integration Layer or a CRM database.
    """
    mock_profiles = [
        {
            "id": "KYC-9921",
            "entity_name": "Globex Corporation",
            "jurisdiction": "USA",
            "risk_score": 12,
            "status": "CLEARED",
            "last_reviewed": "2023-10-12T10:00:00Z"
        },
        {
            "id": "KYC-8834",
            "entity_name": "Stark Industries",
            "jurisdiction": "UK",
            "risk_score": 85,
            "status": "HIGH_RISK",
            "last_reviewed": "2023-11-05T14:30:00Z"
        },
        {
            "id": "KYC-7745",
            "entity_name": "Acme Corp",
            "jurisdiction": "CayMAN_ISLANDS",
            "risk_score": 92,
            "status": "UNDER_REVIEW",
            "last_reviewed": "2023-11-20T09:15:00Z"
        },
        {
            "id": "KYC-6656",
            "entity_name": "Initech",
            "jurisdiction": "USA",
            "risk_score": 25,
            "status": "CLEARED",
            "last_reviewed": "2023-08-22T16:45:00Z"
        },
        {
            "id": "KYC-5567",
            "entity_name": "Soylent Corp",
            "jurisdiction": "GERMANY",
            "risk_score": 60,
            "status": "PENDING",
            "last_reviewed": "2023-11-21T11:00:00Z"
        }
    ]
    return {
        "items": mock_profiles,
        "total": len(mock_profiles)
    }
