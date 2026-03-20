from __future__ import annotations

from datetime import datetime

from incident_agent.analysis.correlator import correlate_incidents
from incident_agent.schemas.events import LogEvent, MetricPoint


def test_correlate_incidents_groups_error_logs_by_service() -> None:
    logs = [
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T10:00:00"),
            service="api-service",
            severity="ERROR",
            message="Database timeout",
        ),
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T10:01:00"),
            service="api-service",
            severity="CRITICAL",
            message="Request failure burst",
        ),
    ]
    metrics = [
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T10:00:30"),
            service="api-service",
            metric_name="cpu_usage",
            value=92.0,
            unit="percent",
        )
    ]

    incidents = correlate_incidents(logs=logs, metrics=metrics)

    assert len(incidents) == 1
    assert incidents[0].service == "api-service"
    assert len(incidents[0].related_metrics) == 1
