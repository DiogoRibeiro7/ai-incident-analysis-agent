"""Caching wrapper for deterministic LLM calls."""

from __future__ import annotations

import logging

from incident_agent.llm.base import BaseLLMProvider
from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
)
from incident_agent.utils.observability import get_logger, log_event
from incident_agent.utils.resilience import JsonFileCache, stable_cache_key

logger = get_logger(__name__)


class CachedLLMProvider(BaseLLMProvider):
    """Cache deterministic provider responses on disk."""

    def __init__(self, provider: BaseLLMProvider, *, cache_dir: str) -> None:
        self._provider = provider
        self._cache = JsonFileCache(cache_dir)

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        cache_key = self._completion_key(request)
        if cache_key is not None:
            cached = self._cache.read(cache_key)
            if cached is not None:
                log_event(
                    logger,
                    level=logging.INFO,
                    event="llm.cache.hit",
                    message="served completion from cache",
                    model=request.model,
                )
                return LLMCompletionResponse.model_validate(cached)

        response = self._provider.complete(request)
        if cache_key is not None:
            self._cache.write(cache_key, response.model_dump(mode="json"))
            log_event(
                logger,
                level=logging.INFO,
                event="llm.cache.store",
                message="stored completion in cache",
                model=request.model,
            )
        return response

    def generate_structured_report(
        self,
        request: LLMStructuredReportRequest,
    ) -> LLMStructuredReportResponse:
        cache_key = self._structured_key(request)
        if cache_key is not None:
            cached = self._cache.read(cache_key)
            if cached is not None:
                log_event(
                    logger,
                    level=logging.INFO,
                    event="llm.cache.hit",
                    message="served structured report from cache",
                    model=request.model,
                )
                return LLMStructuredReportResponse.model_validate(cached)

        response = self._provider.generate_structured_report(request)
        if cache_key is not None:
            self._cache.write(cache_key, response.model_dump(mode="json"))
            log_event(
                logger,
                level=logging.INFO,
                event="llm.cache.store",
                message="stored structured report in cache",
                model=request.model,
            )
        return response

    def _completion_key(self, request: LLMCompletionRequest) -> str | None:
        if request.temperature != 0.0:
            return None
        return stable_cache_key("completion", request.model_dump(mode="json"))

    def _structured_key(self, request: LLMStructuredReportRequest) -> str | None:
        if request.temperature != 0.0:
            return None
        return stable_cache_key("structured_report", request.model_dump(mode="json"))
