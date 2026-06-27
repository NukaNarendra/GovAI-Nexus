import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError
from groq import AsyncGroq

logger = logging.getLogger(__name__)


class GroqClientError(Exception):
    pass


class RateLimitError(GroqClientError):
    pass


class OutputParsingError(GroqClientError):
    pass


class ModelNotFoundError(GroqClientError):
    pass


class GroqClientManager:
    def __init__(
        self,
        api_key: str,
        default_model: str = "llama-3.1-70b-versatile",
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")

        self.client = AsyncGroq(api_key=api_key, timeout=timeout, max_retries=0)
        self.default_model = default_model
        self.max_retries = max_retries

        self.supported_models = [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ]

        self.metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "prompt_tokens_total": 0,
            "completion_tokens_total": 0,
            "total_tokens_total": 0,
        }

    def _validate_model(self, model: str) -> None:
        if model not in self.supported_models:
            logger.warning(
                f"Model {model} is not in the explicitly supported list, but proceeding."
            )

    async def _execute_with_retry(self, coro_func, *args, **kwargs) -> Any:
        last_exception = None
        base_delay = 1.0

        for attempt in range(self.max_retries):
            try:
                self.metrics["total_requests"] += 1
                return await coro_func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                if "rate limit" in error_str or "429" in error_str:
                    logger.warning(
                        f"Groq Rate limit hit. Attempt {attempt + 1}/{self.max_retries}"
                    )
                    await asyncio.sleep(base_delay * (2**attempt))
                    continue

                if "timeout" in error_str or "502" in error_str or "503" in error_str:
                    logger.warning(
                        f"Groq Server error/timeout. Attempt {attempt + 1}/{self.max_retries}"
                    )
                    await asyncio.sleep(base_delay * (2**attempt))
                    continue

                self.metrics["failed_requests"] += 1
                logger.error(f"Fatal Groq error: {str(e)}")
                raise GroqClientError(
                    f"Failed to communicate with Groq: {str(e)}"
                ) from e

        self.metrics["failed_requests"] += 1
        raise RateLimitError(
            f"Exhausted {self.max_retries} retries connecting to Groq."
        ) from last_exception

    def _update_token_metrics(self, usage: Any) -> None:
        if hasattr(usage, "prompt_tokens"):
            self.metrics["prompt_tokens_total"] += usage.prompt_tokens
        if hasattr(usage, "completion_tokens"):
            self.metrics["completion_tokens_total"] += usage.completion_tokens
        if hasattr(usage, "total_tokens"):
            self.metrics["total_tokens_total"] += usage.total_tokens

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_completion_tokens: int = 4096,
        top_p: float = 1.0,
    ) -> Dict[str, Any]:
        target_model = model or self.default_model
        self._validate_model(target_model)

        formatted_messages: Any = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]

        async def _call_api():
            return await self.client.chat.completions.create(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                top_p=top_p,
            )

        response = await self._execute_with_retry(_call_api)
        self._update_token_metrics(response.usage)

        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "model_used": target_model,
            "finish_reason": response.choices[0].finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def generate_json_structured_output(
        self,
        messages: List[Dict[str, str]],
        response_schema: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        target_model = model or self.default_model
        self._validate_model(target_model)

        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)

        system_instruction = (
            "You are a strict data extraction system. You MUST respond ONLY with valid JSON "
            "that strictly conforms to the following JSON schema. Do not include markdown formatting, "
            "do not include explanations. Only return the raw JSON object.\n\n"
            f"SCHEMA:\n{schema_json}"
        )

        injected_messages = [
            {"role": "system", "content": system_instruction}
        ] + messages

        # FIX: Using 'Any' prevents the IDE linter from showing red squiggly lines
        formatted_messages: Any = [
            {"role": m["role"], "content": m["content"]} for m in injected_messages
        ]

        async def _call_api():
            return await self.client.chat.completions.create(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )

        response = await self._execute_with_retry(_call_api)
        self._update_token_metrics(response.usage)

        raw_content = response.choices[0].message.content

        try:
            parsed_json = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse Groq response as JSON. Raw output: {raw_content[:200]}..."
            )
            raise OutputParsingError(f"LLM did not return valid JSON: {str(e)}")

        try:
            validated_data = response_schema(**parsed_json)
        except ValidationError as e:
            logger.error(f"JSON matches format but violates schema. Errors: {e.json()}")
            raise OutputParsingError(f"LLM output violates required schema: {str(e)}")

        return {
            "parsed_data": validated_data.model_dump(),
            "model_used": target_model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def analyze_document_risk(
        self, document_text: str, risk_schema: Type[BaseModel]
    ) -> Dict[str, Any]:
        messages = [
            {
                "role": "user",
                "content": f"Analyze the following financial document and extract risk indicators according to the schema.\n\nDOCUMENT:\n{document_text}",
            }
        ]

        return await self.generate_json_structured_output(
            messages=messages,
            response_schema=risk_schema,
            model="llama-3.1-70b-versatile",
            temperature=0.1,
        )

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        return dict(self.metrics)
