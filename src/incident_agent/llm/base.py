"""LLM provider abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod

from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
)
from incident_agent.schemas.report import IncidentReport


class LLMProviderError(RuntimeError):
    """Base error for provider failures."""


class LLMTimeoutError(LLMProviderError):
    """Raised when provider requests timeout."""


class LLMRateLimitError(LLMProviderError):
    """Raised when provider returns rate-limit responses."""


class LLMResponseFormatError(LLMProviderError):
    """Raised when provider returns malformed structured output."""


class BaseLLMProvider(ABC):
    """Base abstraction for incident-report generation providers."""

    @abstractmethod
    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        """Generate plain text completion."""

    @abstractmethod
    def generate_structured_report(
        self,
        request: LLMStructuredReportRequest,
    ) -> LLMStructuredReportResponse:
        """Generate a structured incident report response body."""

    def generate_incident_report(self, prompt: str, model: str) -> IncidentReport:
        """Generate and parse a structured incident report."""

        response = self.generate_structured_report(
            LLMStructuredReportRequest(prompt=prompt, model=model)
        )
        try:
            return IncidentReport.model_validate_json(response.content)
        except ValueError as error:
            raise LLMResponseFormatError(
                "Provider returned malformed incident report JSON."
            ) from error
