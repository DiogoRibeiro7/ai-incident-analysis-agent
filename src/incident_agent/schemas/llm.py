"""Schemas for LLM provider requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMUsage(BaseModel):
    """Usage metadata for one provider response."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    estimated_cost_usd: float | None = None


class LLMCompletionRequest(BaseModel):
    """Plain completion request."""

    prompt: str
    model: str
    temperature: float = 0.0
    max_output_tokens: int = 1200


class LLMCompletionResponse(BaseModel):
    """Plain completion response."""

    model: str
    content: str
    raw_response: dict[str, object]
    usage: LLMUsage = Field(default_factory=LLMUsage)


class LLMStructuredReportRequest(BaseModel):
    """Structured incident report request."""

    prompt: str
    model: str
    temperature: float = 0.0
    max_output_tokens: int = 1200


class LLMStructuredReportResponse(BaseModel):
    """Structured incident report response."""

    model: str
    content: str
    raw_response: dict[str, object]
    usage: LLMUsage = Field(default_factory=LLMUsage)
