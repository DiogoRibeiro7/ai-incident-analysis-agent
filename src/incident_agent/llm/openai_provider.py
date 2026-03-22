"""OpenAI-backed provider implementation."""

from __future__ import annotations

import logging
import os
import time

import httpx

from incident_agent.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseFormatError,
    LLMTimeoutError,
)
from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
)
from incident_agent.utils.observability import execution_span, get_logger, log_event

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Provider implementation using OpenAI chat completions API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key or os.getenv("INCIDENT_AGENT_OPENAI_API_KEY")
        if not self._api_key:
            raise LLMProviderError(
                "Missing OpenAI API key. Set INCIDENT_AGENT_OPENAI_API_KEY environment variable."
            )
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        with execution_span(
            logger,
            event_prefix="provider.call",
            stage="openai.complete",
            provider="openai",
            model=request.model,
        ):
            response_json = self._post_with_retries(payload, model=request.model)
        content = _extract_message_text(response_json)
        return LLMCompletionResponse(
            model=request.model,
            content=content,
            raw_response=response_json,
        )

    def generate_structured_report(
        self,
        request: LLMStructuredReportRequest,
    ) -> LLMStructuredReportResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        with execution_span(
            logger,
            event_prefix="provider.call",
            stage="openai.generate_structured_report",
            provider="openai",
            model=request.model,
        ):
            response_json = self._post_with_retries(payload, model=request.model)
        content = _extract_message_text(response_json)
        try:
            # Ensure it is valid JSON before returning.
            import json

            json.loads(content)
        except ValueError as error:
            raise LLMResponseFormatError("Provider returned malformed JSON content.") from error

        return LLMStructuredReportResponse(
            model=request.model,
            content=content,
            raw_response=response_json,
        )

    def _post_with_retries(self, payload: dict[str, object], *, model: str) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self._base_url}/chat/completions"
        attempt = 0
        while True:
            attempt += 1
            attempt_start = time.perf_counter()
            log_event(
                logger,
                level=logging.INFO,
                event="provider.request.attempt",
                message="sending provider request",
                provider="openai",
                model=model,
                attempt=attempt,
            )
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as error:
                if attempt <= self._max_retries:
                    backoff_seconds = self._retry_backoff_seconds * attempt
                    log_event(
                        logger,
                        level=logging.WARNING,
                        event="provider.request.retry",
                        message="retrying provider request after timeout",
                        provider="openai",
                        model=model,
                        attempt=attempt,
                        reason="timeout",
                        backoff_seconds=backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider request failed after timeout retries",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="timeout",
                )
                raise LLMTimeoutError("OpenAI request timed out.") from error
            except httpx.HTTPError as error:
                if attempt <= self._max_retries:
                    backoff_seconds = self._retry_backoff_seconds * attempt
                    log_event(
                        logger,
                        level=logging.WARNING,
                        event="provider.request.retry",
                        message="retrying provider request after network error",
                        provider="openai",
                        model=model,
                        attempt=attempt,
                        reason="network_error",
                        backoff_seconds=backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider request failed after network retries",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="network_error",
                )
                raise LLMProviderError("OpenAI request failed due to network error.") from error

            if response.status_code == 429:
                if attempt <= self._max_retries:
                    backoff_seconds = self._retry_backoff_seconds * attempt
                    log_event(
                        logger,
                        level=logging.WARNING,
                        event="provider.request.retry",
                        message="retrying provider request after rate limit",
                        provider="openai",
                        model=model,
                        attempt=attempt,
                        reason="rate_limit",
                        status_code=response.status_code,
                        backoff_seconds=backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider request failed after rate limit retries",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="rate_limit",
                    status_code=response.status_code,
                )
                raise LLMRateLimitError("OpenAI rate limit exceeded after retries.")
            if response.status_code >= 500:
                if attempt <= self._max_retries:
                    backoff_seconds = self._retry_backoff_seconds * attempt
                    log_event(
                        logger,
                        level=logging.WARNING,
                        event="provider.request.retry",
                        message="retrying provider request after server error",
                        provider="openai",
                        model=model,
                        attempt=attempt,
                        reason="server_error",
                        status_code=response.status_code,
                        backoff_seconds=backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider request failed after server retries",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="server_error",
                    status_code=response.status_code,
                )
                raise LLMProviderError(f"OpenAI server error: status {response.status_code}.")
            if response.status_code >= 400:
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider request failed with client error",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="client_error",
                    status_code=response.status_code,
                )
                raise LLMProviderError(
                    f"OpenAI request failed with status {response.status_code}: {response.text}"
                )

            try:
                data = response.json()
            except ValueError as error:
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider returned malformed json",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="invalid_json",
                )
                raise LLMResponseFormatError("OpenAI response was not valid JSON.") from error
            if not isinstance(data, dict):
                log_event(
                    logger,
                    level=logging.ERROR,
                    event="provider.request.failed",
                    message="provider returned non-object json",
                    provider="openai",
                    model=model,
                    attempt=attempt,
                    reason="invalid_json_shape",
                )
                raise LLMResponseFormatError("OpenAI response JSON must be an object.")
            duration_ms = round((time.perf_counter() - attempt_start) * 1000, 2)
            log_event(
                logger,
                level=logging.INFO,
                event="provider.request.succeeded",
                message="provider request succeeded",
                provider="openai",
                model=model,
                attempt=attempt,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return data


def _extract_message_text(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseFormatError("Missing choices in provider response.")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMResponseFormatError("Invalid choice payload in provider response.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMResponseFormatError("Missing message object in provider response.")
    content = message.get("content")
    if not isinstance(content, str):
        raise LLMResponseFormatError("Missing text content in provider response.")
    return content
