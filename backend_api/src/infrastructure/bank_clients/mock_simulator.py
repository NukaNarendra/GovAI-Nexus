import asyncio
import uuid
import time
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ValidationError
from enum import Enum
from pydantic import ConfigDict


class BankSimulatorError(Exception):
    pass


class AccountNotFoundError(BankSimulatorError):
    pass


class InsufficientFundsError(BankSimulatorError):
    pass


class KYCValidationError(BankSimulatorError):
    pass


class TransactionStatus(str):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED_COMPLIANCE = "BLOCKED_COMPLIANCE"


class KYCStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    HIGH_RISK = "HIGH_RISK"


class Address(BaseModel):
    street: str
    city: str
    country: str
    postal_code: str


class CorporateEntity(BaseModel):
    entity_id: str
    company_name: str
    registration_number: str
    incorporation_date: str
    country_of_incorporation: str
    beneficial_owners: List[str]
    kyc_status: str
    risk_score: int
    registered_address: Address


class BankAccount(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    account_id: str
    entity_id: str
    account_number: str
    currency: str
    balance: float
    is_active: bool
    daily_limit: float


class Transaction(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount: float
    currency: str
    timestamp: float
    status: str
    metadata: Dict[str, Any]


class MockBankingSimulator:
    def __init__(self, simulate_latency: bool = True, base_latency_ms: int = 150):
        self.simulate_latency = simulate_latency
        self.base_latency_ms = base_latency_ms
        self.entities: Dict[str, CorporateEntity] = {}
        self.accounts: Dict[str, BankAccount] = {}
        self.transactions: Dict[str, Transaction] = {}
        self.sanctions_list: List[str] = [
            "GLOBAL_SHELL_CORP",
            "RESTRICTED_TRADING_LTD",
            "SANCTIONED_OIL_INC",
        ]
        self._seed_initial_data()

    def _seed_initial_data(self) -> None:
        safe_entity = CorporateEntity(
            entity_id="ENT_1001",
            company_name="Acme Tech Innovations",
            registration_number="REG-987654321",
            incorporation_date="2015-06-15",
            country_of_incorporation="USA",
            beneficial_owners=["John Doe", "Jane Smith"],
            kyc_status=KYCStatus.VERIFIED,
            risk_score=15,
            registered_address=Address(
                street="123 Tech Lane",
                city="San Francisco",
                country="USA",
                postal_code="94105",
            ),
        )
        self.entities[safe_entity.entity_id] = safe_entity

        risky_entity = CorporateEntity(
            entity_id="ENT_1002",
            company_name="Global Shell Corp",
            registration_number="REG-000000000",
            incorporation_date="2023-11-01",
            country_of_incorporation="CYM",
            beneficial_owners=["Hidden Owner A"],
            kyc_status=KYCStatus.PENDING,
            risk_score=85,
            registered_address=Address(
                street="PO Box 123",
                city="George Town",
                country="CYM",
                postal_code="KY1-1102",
            ),
        )
        self.entities[risky_entity.entity_id] = risky_entity

        acct_1 = BankAccount(
            account_id="ACC_1001_USD",
            entity_id="ENT_1001",
            account_number="000123456789",
            currency="USD",
            balance=5000000.00,
            is_active=True,
            daily_limit=100000.00,
        )
        self.accounts[acct_1.account_id] = acct_1

    async def _apply_latency(self) -> None:
        if self.simulate_latency:
            jitter = random.uniform(0.5, 1.5)
            sleep_time = (self.base_latency_ms * jitter) / 1000.0
            await asyncio.sleep(sleep_time)

    async def get_entity_kyc_profile(self, entity_id: str) -> Dict[str, Any]:
        await self._apply_latency()
        if entity_id not in self.entities:
            raise BankSimulatorError(
                f"Entity {entity_id} not found in core banking system"
            )
        return self.entities[entity_id].model_dump()

    async def search_entities_by_name(self, company_name: str) -> List[Dict[str, Any]]:
        await self._apply_latency()
        results = []
        for entity in self.entities.values():
            if company_name.lower() in entity.company_name.lower():
                results.append(entity.model_dump())
        return results

    async def onboard_new_corporate_client(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        await self._apply_latency()
        try:
            new_entity = CorporateEntity(**payload)
        except ValidationError as e:
            raise KYCValidationError(f"Invalid corporate entity payload: {str(e)}")

        if new_entity.company_name in self.sanctions_list:
            new_entity.kyc_status = KYCStatus.REJECTED
            new_entity.risk_score = 99

        self.entities[new_entity.entity_id] = new_entity
        return new_entity.model_dump()

    async def update_kyc_status(
        self, entity_id: str, new_status: str, audit_reason: str
    ) -> Dict[str, Any]:
        await self._apply_latency()
        if entity_id not in self.entities:
            raise BankSimulatorError(f"Entity {entity_id} not found")

        entity = self.entities[entity_id]
        entity.kyc_status = new_status
        return {
            "entity_id": entity_id,
            "updated_status": new_status,
            "audit_trail": audit_reason,
        }

    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        await self._apply_latency()
        if account_id not in self.accounts:
            raise AccountNotFoundError(f"Account {account_id} not found")

        account = self.accounts[account_id]
        return {
            "account_id": account.account_id,
            "currency": account.currency,
            "available_balance": account.balance,
            "is_active": account.is_active,
        }

    async def list_entity_accounts(self, entity_id: str) -> List[Dict[str, Any]]:
        await self._apply_latency()
        results = []
        for account in self.accounts.values():
            if account.entity_id == entity_id:
                results.append(account.model_dump())
        return results

    async def execute_wire_transfer(
        self,
        source_account: str,
        destination_account: str,
        amount: float,
        currency: str,
        metadata: dict[str, Any] = None,
    ) -> dict[str, Any]:
        await self._apply_latency()

        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"

        if source_account not in self.accounts:
            raise AccountNotFoundError(f"Source account {source_account} invalid")

        src_acct = self.accounts[source_account]

        if not src_acct.is_active:
            raise BankSimulatorError(
                f"Source account {source_account} is frozen or inactive"
            )

        if src_acct.currency != currency:
            raise BankSimulatorError(
                "Cross-currency mock transfers not supported in this sandbox yet"
            )

        if src_acct.balance < amount:
            raise InsufficientFundsError(
                f"Account {source_account} lacks available funds"
            )

        if amount > src_acct.daily_limit:
            raise BankSimulatorError(
                f"Amount exceeds daily limit of {src_acct.daily_limit}"
            )

        src_acct.balance -= amount

        if destination_account in self.accounts:
            dest_acct = self.accounts[destination_account]
            dest_acct.balance += amount

        txn = Transaction(
            transaction_id=transaction_id,
            source_account=source_account,
            destination_account=destination_account,
            amount=amount,
            currency=currency,
            timestamp=time.time(),
            status=TransactionStatus.COMPLETED,
            metadata=metadata or {},
        )

        self.transactions[transaction_id] = txn
        return txn.model_dump()

    async def simulate_inbound_wire(
        self,
        destination_account: str,
        amount: float,
        currency: str,
        origin_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self._apply_latency()

        transaction_id = f"TXN_IN_{uuid.uuid4().hex[:12].upper()}"

        if destination_account not in self.accounts:
            raise AccountNotFoundError(
                f"Destination account {destination_account} invalid"
            )

        dest_acct = self.accounts[destination_account]
        dest_acct.balance += amount

        txn = Transaction(
            transaction_id=transaction_id,
            source_account=origin_details.get("sender_iban", "UNKNOWN_EXTERNAL"),
            destination_account=destination_account,
            amount=amount,
            currency=currency,
            timestamp=time.time(),
            status=TransactionStatus.COMPLETED,
            metadata=origin_details,
        )

        self.transactions[transaction_id] = txn
        return txn.model_dump()

    async def get_transaction_history(
        self, account_id: str, days_back: int = 30
    ) -> List[Dict[str, Any]]:
        await self._apply_latency()
        results = []
        cutoff_time = time.time() - (days_back * 86400)

        for txn in self.transactions.values():
            if (
                txn.source_account == account_id
                or txn.destination_account == account_id
            ) and txn.timestamp >= cutoff_time:
                results.append(txn.model_dump())

        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results

    async def check_aml_sanctions(self, name: str) -> Dict[str, Any]:
        await self._apply_latency()
        match_found = False
        match_score = 0.0

        normalized_name = name.lower().strip()

        for sanctioned_entity in self.sanctions_list:
            if normalized_name in sanctioned_entity.lower():
                match_found = True
                match_score = 100.0
                break

            parts = normalized_name.split()
            for part in parts:
                if len(part) > 4 and part in sanctioned_entity.lower():
                    match_found = True
                    match_score = max(match_score, 65.0)

        return {
            "entity_checked": name,
            "sanctions_hit": match_found,
            "confidence_score": match_score,
            "database_version": "2024.10.15",
            "timestamp": time.time(),
        }

    async def freeze_account(self, account_id: str, reason_code: str) -> Dict[str, Any]:
        await self._apply_latency()
        if account_id not in self.accounts:
            raise AccountNotFoundError(f"Account {account_id} not found")

        account = self.accounts[account_id]
        account.is_active = False

        return {
            "account_id": account_id,
            "status": "FROZEN",
            "reason": reason_code,
            "timestamp": time.time(),
        }

    async def generate_mock_bank_statement(
        self, account_id: str, month: int, year: int
    ) -> str:
        await self._apply_latency()
        if account_id not in self.accounts:
            raise AccountNotFoundError(f"Account {account_id} not found")

        history = await self.get_transaction_history(account_id, days_back=60)

        statement_text = (
            f"BANK STATEMENT\nACCOUNT: {account_id}\nPERIOD: {month}/{year}\n"
        )
        statement_text += "-" * 50 + "\n"
        statement_text += "DATE       | TYPE | AMOUNT      | BALANCE\n"
        statement_text += "-" * 50 + "\n"

        running_balance = self.accounts[account_id].balance

        for txn in history:
            dt = datetime.fromtimestamp(txn["timestamp"]).strftime("%Y-%m-%d")
            t_type = "CR" if txn["destination_account"] == account_id else "DR"
            statement_text += (
                f"{dt} |  {t_type}  | {txn['amount']:10.2f} | {running_balance:10.2f}\n"
            )

            if t_type == "CR":
                running_balance -= txn["amount"]
            else:
                running_balance += txn["amount"]

        return statement_text
