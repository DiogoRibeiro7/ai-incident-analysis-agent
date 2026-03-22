"""Application settings and configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application.

    Environment variables can override these values. A YAML config file can
    also be loaded by calling :func:`load_settings_from_yaml`.
    """

    model_config = SettingsConfigDict(env_prefix="INCIDENT_AGENT_", extra="ignore")

    app_name: str = Field(default="ai-incident-analysis-agent")
    environment: str = Field(default="local")
    llm_provider: str = Field(default="mock")
    log_level: str = Field(default="INFO")
    json_logs: bool = Field(default=True)


class ObservabilityConfig(BaseModel):
    """Logging and tracing runtime configuration."""

    log_level: str = "INFO"
    json_logs: bool = True


def load_settings_from_yaml(path: Path) -> dict[str, Any]:
    """Load settings from a YAML file.

    Parameters
    ----------
    path:
        Path to a YAML configuration file.
    """

    with path.open("r", encoding="utf-8") as handle:
        loaded: dict[str, Any] = yaml.safe_load(handle) or {}
    return loaded


def load_observability_config(path: str | Path = "configs/default.yaml") -> ObservabilityConfig:
    """Load observability config from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("observability", {})
    if not isinstance(section, dict):
        raise ValueError("The 'observability' section must be a mapping.")
    return ObservabilityConfig.model_validate(section)
