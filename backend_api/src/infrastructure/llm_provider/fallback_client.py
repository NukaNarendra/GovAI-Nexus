import json
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class FallbackProviderError(Exception):
    pass


class ProviderState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class LLMRouter:
    def __init__(
        self,
        primary_client: Any,
        secondary_client: Optional[Any] = None,
        max_failures_before_switch: int = 3,
    ):
        self.primary_client = primary_client
        self.secondary_client = secondary_client
        self.max_failures = max_failures_before_switch
        self.primary_failures = 0
        self.state = ProviderState.HEALTHY

    def _handle_primary_failure(self) -> None:
        self.primary_failures += 1
        if self.primary_failures >= self.max_failures:
            if self.secondary_client:
                logger.warning(
                    "Primary LLM provider failed threshold. Switching to secondary provider."
                )
                self.state = ProviderState.DEGRADED
            else:
                logger.error(
                    "Primary LLM provider failed, and no secondary provider is configured."
                )
                self.state = ProviderState.OFFLINE

    def reset_state(self) -> None:
        self.primary_failures = 0
        self.state = ProviderState.HEALTHY
        logger.info("LLM Router state reset to HEALTHY")

    async def generate_response_with_fallback(
        self,
        messages: List[Any],
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        if self.state == ProviderState.HEALTHY or self.state == ProviderState.DEGRADED:
            try:
                if schema:
                    response = (
                        await self.primary_client.generate_json_structured_output(
                            messages=messages,
                            response_schema=schema,
                            temperature=temperature,
                        )
                    )
                else:
                    response_obj = await self.primary_client.generate_chat_completion(
                        messages=messages, temperature=temperature
                    )
                    response = {
                        "content": response_obj.content,
                        "usage": response_obj.usage.model_dump(),
                    }

                self.primary_failures = max(0, self.primary_failures - 1)
                return response

            except Exception as e:
                logger.error(f"Primary LLM provider failed: {str(e)}")
                self._handle_primary_failure()

        if self.state == ProviderState.DEGRADED and self.secondary_client:
            logger.info("Attempting request with secondary LLM provider")
            try:
                if schema:
                    return await self.secondary_client.generate_json_structured_output(
                        messages=messages,
                        response_schema=schema,
                        temperature=temperature,
                    )
                else:
                    response_obj = await self.secondary_client.generate_chat_completion(
                        messages=messages, temperature=temperature
                    )
                    return {
                        "content": response_obj.content,
                        "usage": response_obj.usage.model_dump(),
                    }
            except Exception as e:
                logger.error(f"Secondary LLM provider also failed: {str(e)}")
                self.state = ProviderState.OFFLINE
                raise FallbackProviderError(
                    "Both primary and secondary LLM providers failed"
                ) from e

        if self.state == ProviderState.OFFLINE:
            logger.critical(
                "All LLM providers offline. Entering emergency fallback mode."
            )
            return self._emergency_heuristic_fallback(messages, schema)

        raise FallbackProviderError("Unexpected router state")

    def _emergency_heuristic_fallback(
        self, messages: List[Any], schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        prompt_text = " ".join(
            [m.content.lower() for m in messages if hasattr(m, "content")]
        )

        is_approval = "approve" in prompt_text and "safe" in prompt_text
        is_rejection = (
            "block" in prompt_text
            or "sanction" in prompt_text
            or "fraud" in prompt_text
        )

        fallback_decision = "MANUAL_REVIEW_REQUIRED"
        confidence = 0.0

        if is_approval and not is_rejection:
            fallback_decision = "APPROVED"
            confidence = 0.5
        elif is_rejection:
            fallback_decision = "REJECTED"
            confidence = 0.9

        if schema:
            return {
                "decision": fallback_decision,
                "confidence_score": confidence,
                "reasoning": "SYSTEM DEGRADED: Decision made by emergency keyword heuristic. Requires HITL review.",
                "requires_human_review": True,
                "risk_flags": ["LLM_OFFLINE_FALLBACK"],
            }
        else:
            return {
                "content": f"SYSTEM DEGRADED. Suggested Action: {fallback_decision}. Please review manually.",
                "usage": {"total_tokens": 0},
            }
