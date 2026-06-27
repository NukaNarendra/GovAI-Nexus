from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_user

router = APIRouter()

@router.get("/watchlists", response_model=Dict[str, Any])
async def get_aml_watchlists(
    current_user = Depends(get_current_user)
) -> Any:
    """
    Get a simulated list of AML watchlist hits.
    In a real implementation, this would query external sanctions databases (OFAC, UN, etc.).
    """
    mock_watchlists = [
        {
            "id": "AML-1001",
            "target_name": "John Doe",
            "match_type": "PEP",
            "confidence_score": 98,
            "status": "CONFIRMED",
            "source": "Global PEP List"
        },
        {
            "id": "AML-1002",
            "target_name": "Jane Smith",
            "match_type": "SANCTIONS",
            "confidence_score": 85,
            "status": "INVESTIGATING",
            "source": "OFAC SDN"
        },
        {
            "id": "AML-1003",
            "target_name": "Robert Tables",
            "match_type": "ADVERSE_MEDIA",
            "confidence_score": 45,
            "status": "FALSE_POSITIVE",
            "source": "Dow Jones"
        },
        {
            "id": "AML-1004",
            "target_name": "Alice Wonderland",
            "match_type": "SANCTIONS",
            "confidence_score": 92,
            "status": "CONFIRMED",
            "source": "EU Consolidated List"
        }
    ]
    return {
        "items": mock_watchlists,
        "total": len(mock_watchlists)
    }
