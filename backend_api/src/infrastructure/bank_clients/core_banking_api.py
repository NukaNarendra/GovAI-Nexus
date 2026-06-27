import asyncio
import time
import uuid
import json
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import httpx


class APIClientError(Exception):
    pass


class UnauthorizedError(APIClientError):
    pass


class ResourceNotFoundError(APIClientError):
    pass


class PayloadValidationError(APIClientError):
    pass


class ServiceUnavailableError(APIClientError):
    pass


class CircuitBreakerOpenError(APIClientError):
    pass


class BankEnvironment(str, Enum):
    SANDBOX = "sandbox"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ResilientCircuitBreaker:
    def __init__(
        self, failure_threshold: int = 5, recovery_timeout_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def record_failure(self) -> None:
        async with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN

    async def record_success(self) -> None:
        async with self._lock:
            self.failures = 0
            self.state = CircuitState.CLOSED

    async def can_execute(self) -> bool:
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            if self.state == CircuitState.HALF_OPEN:
                return True
            return False


class CoreBankingAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        client_secret: str,
        environment: BankEnvironment = BankEnvironment.SANDBOX,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client_secret = client_secret
        self.environment = environment
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.circuit_breaker = ResilientCircuitBreaker()
        self.session_token = None
        self.token_expiry = 0.0

    async def _get_auth_headers(self) -> Dict[str, str]:
        await self._ensure_valid_token()
        return {
            "Authorization": f"Bearer {self.session_token}",
            "X-Client-Id": self.api_key,
            "X-Environment": self.environment.value,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Correlation-Id": str(uuid.uuid4()),
        }

    async def _ensure_valid_token(self) -> None:
        if self.session_token and time.time() < self.token_expiry - 300:
            return

        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.client_secret,
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            self.session_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self.token_expiry = time.time() + expires_in
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise UnauthorizedError("Failed to authenticate with Core Banking API")
            raise APIClientError(f"Auth request failed: {str(e)}")
        except Exception as e:
            raise APIClientError(f"Unexpected error during authentication: {str(e)}")

    def _calculate_backoff(self, attempt: int) -> float:
        return min(2**attempt + 0.5, 15.0)

    async def _execute_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        if not await self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker prevents call to {endpoint}"
            )

        url = f"{self.base_url}{endpoint}"
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                headers = await self._get_auth_headers()
                if "headers" in kwargs:
                    kwargs["headers"].update(headers)
                else:
                    kwargs["headers"] = headers

                response = await self.client.request(method, url, **kwargs)

                if response.status_code >= 400:
                    self._handle_http_error(response)

                await self.circuit_breaker.record_success()

                if response.status_code == 204:
                    return {}
                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                await self.circuit_breaker.record_failure()
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self._calculate_backoff(attempt))
                else:
                    raise ServiceUnavailableError(
                        f"Connection failed after {self.max_retries} attempts"
                    ) from e
            except APIClientError as e:
                if isinstance(
                    e,
                    (UnauthorizedError, PayloadValidationError, ResourceNotFoundError),
                ):
                    raise e
                last_exception = e
                await self.circuit_breaker.record_failure()
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self._calculate_backoff(attempt))
                else:
                    raise e
            except Exception as e:
                await self.circuit_breaker.record_failure()
                raise APIClientError(f"Critical error executing request: {str(e)}")

        raise APIClientError("Request failed") from last_exception

    def _handle_http_error(self, response: httpx.Response) -> None:
        status = response.status_code
        try:
            error_data = response.json()
        except ValueError:
            error_data = {"error": response.text}

        error_msg = f"API Error [{status}]: {json.dumps(error_data)}"

        if status == 400:
            raise PayloadValidationError(error_msg)
        if status in (401, 403):
            raise UnauthorizedError(error_msg)
        if status == 404:
            raise ResourceNotFoundError(error_msg)
        if status == 422:
            raise PayloadValidationError(error_msg)
        if status == 429:
            raise ServiceUnavailableError(
                f"Rate limited by Core Banking API: {error_msg}"
            )
        if status >= 500:
            raise ServiceUnavailableError(f"Upstream server error: {error_msg}")

        raise APIClientError(error_msg)

    async def get_customer_kyc(self, customer_id: str) -> Dict[str, Any]:
        return await self._execute_request("GET", f"/v2/customers/{customer_id}/kyc")

    async def create_corporate_customer(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._execute_request(
            "POST", "/v2/customers/corporate", json=payload
        )

    async def update_customer_status(
        self, customer_id: str, status: str, reason: str
    ) -> Dict[str, Any]:
        payload = {"status": status, "reason_code": reason}
        return await self._execute_request(
            "PATCH", f"/v2/customers/{customer_id}/status", json=payload
        )

    async def get_account_details(self, account_id: str) -> Dict[str, Any]:
        return await self._execute_request("GET", f"/v2/accounts/{account_id}")

    async def list_customer_accounts(self, customer_id: str) -> List[Dict[str, Any]]:
        response = await self._execute_request(
            "GET", f"/v2/customers/{customer_id}/accounts"
        )
        return response.get("accounts", [])

    async def execute_transfer(
        self,
        source_id: str,
        destination_id: str,
        amount: float,
        currency: str,
        reference: str,
    ) -> Dict[str, Any]:
        payload = {
            "source_account_id": source_id,
            "destination_account_id": destination_id,
            "amount": {"value": amount, "currency": currency},
            "reference": reference,
            "transfer_type": "INTERNAL_WIRE",
        }
        return await self._execute_request("POST", "/v2/transfers", json=payload)

    async def block_account(
        self, account_id: str, compliance_reason: str
    ) -> Dict[str, Any]:
        payload = {
            "action": "BLOCK",
            "reason": "COMPLIANCE_HOLD",
            "details": compliance_reason,
        }
        return await self._execute_request(
            "POST", f"/v2/accounts/{account_id}/holds", json=payload
        )

    async def screen_entity_against_sanctions(
        self, entity_name: str, country_code: str
    ) -> Dict[str, Any]:
        payload = {
            "entity_name": entity_name,
            "country_of_registration": country_code,
            "list_types": ["OFAC", "UN", "EU", "HMT"],
        }
        return await self._execute_request(
            "POST", "/v2/compliance/screen", json=payload
        )

    async def get_transaction_ledger(
        self, account_id: str, start_date: str, end_date: str, limit: int = 100
    ) -> Dict[str, Any]:
        params = {"start_date": start_date, "end_date": end_date, "limit": limit}
        return await self._execute_request(
            "GET", f"/v2/accounts/{account_id}/transactions", params=params
        )

    async def close(self) -> None:
        await self.client.aclose()
