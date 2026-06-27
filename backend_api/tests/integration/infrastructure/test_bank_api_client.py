import pytest
import asyncio
from typing import Dict, Any
import httpx
from src.infrastructure.bank_clients.core_banking_api import (
    CoreBankingAPIClient,
    BankEnvironment,
    CircuitBreakerOpenError,
    UnauthorizedError,
    PayloadValidationError,
    ResourceNotFoundError,
)


@pytest.fixture
async def bank_client() -> CoreBankingAPIClient:
    client = CoreBankingAPIClient(
        base_url="https://mock.sandbox.bank",
        api_key="test_key",
        client_secret="test_secret",
        environment=BankEnvironment.SANDBOX,
        timeout_seconds=2.0,
        max_retries=2,
    )
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_bank_client_auth_token_caching(
    bank_client: CoreBankingAPIClient, httpx_mock
) -> None:
    httpx_mock.add_response(
        url="https://mock.sandbox.bank/oauth/token",
        method="POST",
        json={
            "access_token": "mock_jwt_123",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )

    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/customers/CUST_123/kyc",
        method="GET",
        json={"status": "VERIFIED"},
    )

    result1 = await bank_client.get_customer_kyc("CUST_123")
    assert result1["status"] == "VERIFIED"
    assert bank_client.session_token == "mock_jwt_123"

    result2 = await bank_client.get_customer_kyc("CUST_123")
    assert result2["status"] == "VERIFIED"

    auth_requests = [
        req for req in httpx_mock.get_requests() if "oauth/token" in str(req.url)
    ]
    assert len(auth_requests) == 1


@pytest.mark.asyncio
async def test_bank_client_circuit_breaker_trips_and_recovers(
    bank_client: CoreBankingAPIClient, httpx_mock
) -> None:
    bank_client.circuit_breaker.failure_threshold = 3
    bank_client.circuit_breaker.recovery_timeout = 0.5

    httpx_mock.add_response(
        url="https://mock.sandbox.bank/oauth/token",
        method="POST",
        json={"access_token": "mock_jwt_123", "expires_in": 3600},
    )

    httpx_mock.add_exception(
        httpx.ConnectError("Connection refused"),
        url="https://mock.sandbox.bank/v2/accounts/ACC_1",
    )

    with pytest.raises(Exception):
        await bank_client.get_account_details("ACC_1")

    assert bank_client.circuit_breaker.failures == 1

    with pytest.raises(Exception):
        await bank_client.get_account_details("ACC_1")
    with pytest.raises(Exception):
        await bank_client.get_account_details("ACC_1")

    assert bank_client.circuit_breaker.state.value == "OPEN"

    with pytest.raises(CircuitBreakerOpenError):
        await bank_client.get_account_details("ACC_1")

    await asyncio.sleep(0.6)

    httpx_mock.reset()
    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/accounts/ACC_1",
        method="GET",
        json={"balance": 1000},
    )

    result = await bank_client.get_account_details("ACC_1")
    assert result["balance"] == 1000
    assert bank_client.circuit_breaker.state.value == "CLOSED"
    assert bank_client.circuit_breaker.failures == 0


@pytest.mark.asyncio
async def test_bank_client_error_mapping(
    bank_client: CoreBankingAPIClient, httpx_mock
) -> None:
    bank_client.session_token = "valid_token"
    bank_client.token_expiry = 9999999999.0

    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/customers/INVALID",
        method="GET",
        status_code=404,
        json={"error": "Customer not found"},
    )
    with pytest.raises(ResourceNotFoundError) as exc:
        await bank_client.get_customer_kyc("INVALID")
    assert "404" in str(exc.value)

    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/transfers",
        method="POST",
        status_code=422,
        json={"error": "Amount exceeds limit"},
    )
    with pytest.raises(PayloadValidationError):
        await bank_client.execute_transfer("SRC", "DST", 1000000000.0, "USD", "REF")

    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/accounts/BLOCKED/holds",
        method="POST",
        status_code=403,
        json={"error": "Insufficient permissions to apply hold"},
    )
    with pytest.raises(UnauthorizedError):
        await bank_client.block_account("BLOCKED", "Suspected fraud")


@pytest.mark.asyncio
async def test_bank_client_successful_transfer_execution(
    bank_client: CoreBankingAPIClient, httpx_mock
) -> None:
    bank_client.session_token = "valid_token"
    bank_client.token_expiry = 9999999999.0

    expected_ref = f"CORE_{uuid.uuid4().hex[:8]}"
    httpx_mock.add_response(
        url="https://mock.sandbox.bank/v2/transfers",
        method="POST",
        json={
            "transfer_id": expected_ref,
            "status": "COMPLETED",
            "settled_at": "2024-05-20T10:00:00Z",
        },
    )

    result = await bank_client.execute_transfer(
        source_id="ACC_100",
        destination_id="ACC_200",
        amount=5000.0,
        currency="USD",
        reference="INV-2024-001",
    )

    assert result["transfer_id"] == expected_ref
    assert result["status"] == "COMPLETED"

    requests = httpx_mock.get_requests()
    assert len(requests) == 1

    request_body = requests[0].read().decode("utf-8")
    import json

    parsed_body = json.loads(request_body)
    assert parsed_body["source_account_id"] == "ACC_100"
    assert parsed_body["amount"]["value"] == 5000.0
    assert requests[0].headers["X-Environment"] == "sandbox"
