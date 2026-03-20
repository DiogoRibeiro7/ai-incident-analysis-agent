"""Provider factory and config loading for LLM integrations."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.llm.base import BaseLLMProvider, LLMProviderError
from incident_agent.llm.mock import MockLLMProvider
from incident_agent.llm.openai_provider import OpenAIProvider

ProviderName = Literal["mock", "openai"]


class LLMConfig(BaseModel):
    """Centralized LLM provider and model configuration."""

    provider: ProviderName = "mock"
    report_model: str = "gpt-4.1-mini"
    completion_model: str = "gpt-4.1-mini"
    timeout_seconds: float = 20.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0


def load_llm_config(path: str | Path = "configs/default.yaml") -> LLMConfig:
    """Load LLM config from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("llm", {})
    if not isinstance(section, dict):
        raise ValueError("The 'llm' section must be a mapping.")
    return LLMConfig.model_validate(section)


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """Create provider instance from configuration."""

    if config.provider == "mock":
        return MockLLMProvider()
    if config.provider == "openai":
        return OpenAIProvider(
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
        )
    raise LLMProviderError(f"Unsupported provider '{config.provider}'.")
