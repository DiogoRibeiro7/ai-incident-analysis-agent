"""Interfaces for LLM providers."""

from __future__ import annotations

from typing import Protocol

from incident_agent.schemas.report import IncidentReport


class LLMClient(Protocol):
    """Protocol for incident-report generation backends."""

    def generate_incident_report(self, prompt: str) -> IncidentReport:
        """Generate a structured incident report from a prompt."""
