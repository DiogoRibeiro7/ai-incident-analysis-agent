"""Application settings and configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
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
