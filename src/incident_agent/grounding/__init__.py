"""Grounding validation for generated final reports."""

from incident_agent.core.settings import GroundingConfig
from incident_agent.grounding.validate import validate_report_grounding

__all__ = ["GroundingConfig", "validate_report_grounding"]
