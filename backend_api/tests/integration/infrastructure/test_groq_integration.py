import pytest
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from src.infrastructure.llm_provider.groq_client import (
    GroqClientManager,
    RateLimitError,
    OutputParsingError,
)


class MockRiskSchema(BaseModel):
    risk_level: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    identified_flags: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_human: bool


@pytest.fixture
def groq_manager() -> GroqClientManager:
    return GroqClientManager(
        api_key="mock_key_for_vcr_tests", max_retries=2, timeout=5.0
    )


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_generate_chat_completion_success(
    groq_manager: GroqClientManager,
) -> None:
    messages = [
        {
            "role": "system",
            "content": "You are a helpful banking assistant. Respond in one sentence.",
        },
        {"role": "user", "content": "What is structuring in money laundering?"},
    ]

    response = await groq_manager.generate_chat_completion(
        messages=messages, model="llama-3.1-8b-instant", temperature=0.1
    )

    assert "content" in response
    assert len(response["content"]) > 10
    assert response["role"] == "assistant"
    assert response["usage"]["total_tokens"] > 0
    assert response["model_used"] == "llama-3.1-8b-instant"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_groq_structured_json_output_success(
    groq_manager: GroqClientManager,
) -> None:
    messages = [
        {
            "role": "user",
            "content": "Analyze this profile: John Doe transferred $9,999 to an offshore account in the Cayman Islands. He has no prior history.",
        }
    ]

    response = await groq_manager.generate_json_structured_output(
        messages=messages,
        response_schema=MockRiskSchema,
        model="llama-3.1-70b-versatile",
        temperature=0.0,
    )

    parsed_data = response["parsed_data"]
    assert "risk_level" in parsed_data
    assert parsed_data["risk_level"] in ["HIGH", "CRITICAL", "MEDIUM", "LOW"]
    assert isinstance(parsed_data["identified_flags"], list)
    assert "Cayman Islands" in str(
        parsed_data["identified_flags"]
    ) or "offshore" in str(parsed_data["identified_flags"])
    assert isinstance(parsed_data["confidence"], float)
    assert isinstance(parsed_data["requires_human"], bool)
    assert response["usage"]["prompt_tokens"] > 0


@pytest.mark.asyncio
async def test_groq_handles_invalid_schema_enforcement(mocker) -> None:
    manager = GroqClientManager(api_key="fake", max_retries=1)

    class MockMessage:
        content = '{"risk_level": "UNKNOWN_LEVEL", "identified_flags": "not a list", "confidence": 1.5, "requires_human": "maybe"}'
        role = "assistant"

    class MockChoice:
        message = MockMessage()
        finish_reason = "stop"

    class MockUsage:
        prompt_tokens = 10
        completion_tokens = 10
        total_tokens = 20

    class MockResponse:
        choices = [MockChoice()]
        usage = MockUsage()

    async def mock_create(*args, **kwargs):
        return MockResponse()

    mocker.patch.object(
        manager.client.chat.completions, "create", side_effect=mock_create
    )

    with pytest.raises(OutputParsingError) as exc_info:
        await manager.generate_json_structured_output(
            messages=[{"role": "user", "content": "test"}],
            response_schema=MockRiskSchema,
        )

    assert "violates required schema" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_handles_rate_limits_with_retries(mocker) -> None:
    manager = GroqClientManager(api_key="fake", max_retries=3)

    call_count = 0

    async def mock_create_with_failures(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("HTTP 429 Rate Limit Exceeded")

        class MockResponse:
            class Choice:
                class Message:
                    content = '{"risk_level": "LOW", "identified_flags": [], "confidence": 0.9, "requires_human": false}'
                    role = "assistant"

                message = Message()
                finish_reason = "stop"

            choices = [Choice()]

            class Usage:
                prompt_tokens = 5
                completion_tokens = 5
                total_tokens = 10

            usage = Usage()

        return MockResponse()

    mocker.patch.object(
        manager.client.chat.completions, "create", side_effect=mock_create_with_failures
    )

    response = await manager.generate_json_structured_output(
        messages=[{"role": "user", "content": "test"}], response_schema=MockRiskSchema
    )

    assert call_count == 3
    assert response["parsed_data"]["risk_level"] == "LOW"

    metrics = manager.get_metrics_snapshot()
    assert metrics["failed_requests"] == 0
    assert metrics["total_requests"] == 3


@pytest.mark.asyncio
async def test_groq_exhausts_retries_raises_error(mocker) -> None:
    manager = GroqClientManager(api_key="fake", max_retries=2)

    async def mock_always_fail(*args, **kwargs):
        raise Exception("HTTP 503 Service Unavailable")

    mocker.patch.object(
        manager.client.chat.completions, "create", side_effect=mock_always_fail
    )

    with pytest.raises(RateLimitError) as exc_info:
        await manager.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}]
        )

    assert "Exhausted 2 retries" in str(exc_info.value)
    metrics = manager.get_metrics_snapshot()
    assert metrics["failed_requests"] == 1
