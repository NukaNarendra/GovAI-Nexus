import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from src.api.dependencies import (
    get_db,
    get_current_user,
    get_current_compliance_officer,
)
from src.infrastructure.database.models.user import User
from src.infrastructure.database.models.transaction_record import (
    TransactionRecord,
    TransactionState,
    TransactionType,
)
from src.infrastructure.bank_clients.core_banking_api import (
    CoreBankingAPIClient,
    BankEnvironment,
)
from src.core.config import settings

router = APIRouter()


class ManualExecutionRequest(BaseModel):
    transaction_id: str
    execution_reason: str = Field(..., min_length=10)
    force_override: bool = False


class ExecutionStatusResponse(BaseModel):
    transaction_id: str
    reference_id: str
    status: str
    executed_at: Optional[str]
    core_banking_reference: Optional[str]
    failure_reason: Optional[str]


class BulkExecutionRequest(BaseModel):
    transaction_ids: List[str]
    batch_reference: str


class WebhookPayload(BaseModel):
    event_id: str
    event_type: str
    resource_id: str
    timestamp: str
    payload: Dict[str, Any]
    signature: str


def get_banking_client() -> CoreBankingAPIClient:
    return CoreBankingAPIClient(
        base_url=settings.CORE_BANKING_API_URL,
        api_key=settings.CORE_BANKING_CLIENT_ID,
        client_secret=settings.CORE_BANKING_CLIENT_SECRET,
        environment=BankEnvironment.SANDBOX,
    )


from src.infrastructure.bank_clients.core_banking_adapter import core_banking_system, CoreBankingException

async def _execute_single_transaction_internal(
    db: AsyncSession,
    transaction: TransactionRecord,
    actor_id: str,
) -> Dict[str, Any]:
    if transaction.status != TransactionState.CLEARED and not getattr(
        transaction, "_force_override", False
    ):
        raise ValueError(
            f"Transaction {transaction.id} is not in CLEARED state. Current: {transaction.status}"
        )

    try:
        transaction.transition_state(TransactionState.PROCESSING)
        db.add(transaction)
        await db.commit()

        # Call the new mock core banking adapter
        payload = {
            "source_account": transaction.source_account_id,
            "destination_account": transaction.destination_account_id,
            "amount": transaction.amount,
            "currency": transaction.currency
        }
        api_response = await core_banking_system.post_transaction(
            transaction_id=transaction.id,
            payload=payload
        )

        core_ref = api_response.get("core_reference_id")
        transaction.core_banking_id = core_ref
        transaction.transition_state(TransactionState.EXECUTED)
        db.add(transaction)
        await db.commit()

        return {
            "transaction_id": transaction.id,
            "status": "SUCCESS",
            "core_reference": core_ref,
        }

    except CoreBankingException as e:
        transaction.transition_state(TransactionState.FAILED, reason=str(e))
        db.add(transaction)
        await db.commit()
        return {"transaction_id": transaction.id, "status": "FAILED", "error": str(e)}
    except Exception as e:
        transaction.transition_state(TransactionState.FAILED, reason=str(e))
        db.add(transaction)
        await db.commit()
        return {"transaction_id": transaction.id, "status": "FAILED", "error": str(e)}


@router.post("/manual", response_model=ExecutionStatusResponse)
async def execute_transaction_manually(
    request: ManualExecutionRequest,
    db: AsyncSession = Depends(get_db),
    banking_client: CoreBankingAPIClient = Depends(get_banking_client),
    current_user: User = Depends(get_current_compliance_officer),
) -> Any:
    query = select(TransactionRecord).where(
        TransactionRecord.id == request.transaction_id
    )
    result = await db.execute(query)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction record not found"
        )

    if request.force_override:
        if current_user.role.value != "SYSTEM_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only System Admins can force execution",
            )
        setattr(transaction, "_force_override", True)

    try:
        exec_result = await _execute_single_transaction_internal(
            db, transaction, current_user.id
        )

        return ExecutionStatusResponse(
            transaction_id=transaction.id,
            reference_id=transaction.reference_id,
            status=transaction.status.value,
            executed_at=transaction.executed_at.isoformat()
            if transaction.executed_at
            else None,
            core_banking_reference=transaction.core_banking_id,
            failure_reason=transaction.failure_reason,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/bulk")
async def execute_bulk_transactions(
    request: BulkExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    banking_client: CoreBankingAPIClient = Depends(get_banking_client),
    current_user: User = Depends(get_current_user),
) -> Any:
    if len(request.transaction_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk limit is 100 transactions per request",
        )

    query = select(TransactionRecord).where(
        TransactionRecord.id.in_(request.transaction_ids)
    )
    result = await db.execute(query)
    transactions = result.scalars().all()

    if len(transactions) != len(request.transaction_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more transaction IDs not found",
        )

    cleared_txns = [t for t in transactions if t.status == TransactionState.CLEARED]
    if len(cleared_txns) != len(transactions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All transactions in bulk batch must be in CLEARED state",
        )

    async def _process_bulk(txns: List[TransactionRecord], actor_id: str):
        for tx in txns:
            await _execute_single_transaction_internal(db, tx, actor_id)
            await asyncio.sleep(0.1)

    background_tasks.add_task(_process_bulk, cleared_txns, current_user.id)

    return {
        "status": "ACCEPTED",
        "batch_reference": request.batch_reference,
        "transactions_queued": len(cleared_txns),
        "message": "Bulk execution is processing asynchronously",
    }


@router.get("/{transaction_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    query = select(TransactionRecord).where(TransactionRecord.id == transaction_id)
    result = await db.execute(query)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )

    return ExecutionStatusResponse(
        transaction_id=transaction.id,
        reference_id=transaction.reference_id,
        status=transaction.status.value,
        executed_at=transaction.executed_at.isoformat()
        if transaction.executed_at
        else None,
        core_banking_reference=transaction.core_banking_id,
        failure_reason=transaction.failure_reason,
    )


@router.post("/webhook/core-banking")
async def core_banking_webhook(
    payload: WebhookPayload,
    x_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if not x_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature header"
        )

    if payload.event_type == "TRANSFER_REJECTED":
        query = select(TransactionRecord).where(
            TransactionRecord.core_banking_id == payload.resource_id
        )
        result = await db.execute(query)
        transaction = result.scalar_one_or_none()
        if transaction:
            transaction.transition_state(
                TransactionState.FAILED,
                reason=payload.payload.get("reason", "Upstream rejection"),
            )
            db.add(transaction)
            await db.commit()

    return {"status": "ACK", "event_id": payload.event_id}
