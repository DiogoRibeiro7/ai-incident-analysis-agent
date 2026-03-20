"""Schemas for LLM provider requests and responses."""

from __future__ import annotations

from pydantic import BaseModel


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
