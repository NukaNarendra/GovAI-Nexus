import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CoreBankingException(Exception):
    pass

class CoreBankingAdapter:
    """
    Simulates integration with an external legacy Core Banking System (e.g., Temenos, Mambu).
    This acts as the final ledger boundary where the AI's autonomous decisions are actually executed.
    """
    def __init__(self, system_name: str = "Temenos_T24"):
        self.system_name = system_name
        
    async def post_transaction(self, transaction_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates posting a transaction to the core ledger.
        In a real scenario, this would make an external REST or SOAP API call.
        """
        logger.info(f"[{self.system_name}] Initiating transaction post for {transaction_id}")
        
        # Simulate network latency and legacy system processing time
        await asyncio.sleep(1.5)
        
        if payload.get("amount", 0) > 10000000:
            logger.error(f"[{self.system_name}] Rejected transaction {transaction_id}: Exceeds core banking hard limits")
            raise CoreBankingException("Transaction exceeds global system limits.")
            
        logger.info(f"[{self.system_name}] Successfully posted transaction {transaction_id}")
        
        return {
            "core_reference_id": f"CBS-{transaction_id[-8:].upper()}",
            "status": "SETTLED",
            "ledger_timestamp": "2023-11-20T10:00:00Z"
        }
        
    async def update_kyc_status(self, entity_id: str, status: str) -> Dict[str, Any]:
        """
        Simulates updating a corporate client's KYC profile in the core banking system.
        """
        logger.info(f"[{self.system_name}] Updating KYC status for {entity_id} to {status}")
        await asyncio.sleep(1.0)
        
        return {
            "core_reference_id": f"KYC-{entity_id[-8:].upper()}",
            "status": "UPDATED",
            "effective_date": "2023-11-20"
        }

# Global singleton for the adapter
core_banking_system = CoreBankingAdapter()
