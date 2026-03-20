"""Prompt builders for incident summarisation."""

from __future__ import annotations

from incident_agent.schemas.events import IncidentCandidate


def build_incident_prompt(incident: IncidentCandidate) -> str:
    """Build a grounded prompt from a candidate incident.

    The prompt explicitly asks the model to stay within the provided evidence.
    """

    log_lines = "\n".join(
        f"- {event.timestamp.isoformat()} [{event.severity}] {event.message}"
        for event in incident.related_logs[:10]
    )
    metric_lines = "\n".join(
        f"- {point.timestamp.isoformat()} {point.metric_name}={point.value}"
        for point in incident.related_metrics[:10]
    )

    return (
        "You are an incident analysis assistant. Use only the evidence provided.\n\n"
        f"Service: {incident.service}\n"
        f"Window: {incident.start_time.isoformat()} to {incident.end_time.isoformat()}\n"
        f"Summary: {incident.summary}\n\n"
        f"Logs:\n{log_lines or '- none'}\n\n"
        f"Metrics:\n{metric_lines or '- none'}\n\n"
        "Return a structured report with title, severity, summary, likely root causes, "
        "recommended actions, and evidence items."
    )
