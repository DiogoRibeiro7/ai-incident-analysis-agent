"""Simple correlation logic for grouping logs and metrics into incidents."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from incident_agent.schemas.events import IncidentCandidate, LogEvent, MetricPoint


def correlate_incidents(logs: list[LogEvent], metrics: list[MetricPoint]) -> list[IncidentCandidate]:
    """Correlate suspicious events into simple service-level incident candidates.

    Current heuristic:
    - select ERROR and CRITICAL logs
    - group by service
    - attach metrics within a fixed time window around the log burst
    """

    grouped_logs: dict[str, list[LogEvent]] = defaultdict(list)
    for event in logs:
        if event.severity in {"ERROR", "CRITICAL"}:
            grouped_logs[event.service].append(event)

    incidents: list[IncidentCandidate] = []
    for service, service_logs in grouped_logs.items():
        ordered_logs: list[LogEvent] = sorted(service_logs, key=lambda item: item.timestamp)
        start_time = ordered_logs[0].timestamp
        end_time = ordered_logs[-1].timestamp
        window_start = start_time - timedelta(minutes=10)
        window_end = end_time + timedelta(minutes=10)

        related_metrics: list[MetricPoint] = [
            point
            for point in metrics
            if point.service == service and window_start <= point.timestamp <= window_end
        ]

        incidents.append(
            IncidentCandidate(
                incident_id=f"{service}-{start_time.isoformat()}",
                service=service,
                start_time=start_time,
                end_time=end_time,
                summary=f"Detected {len(ordered_logs)} high-severity log events for {service}.",
                related_logs=ordered_logs,
                related_metrics=related_metrics,
            )
        )

    return sorted(incidents, key=lambda item: item.start_time)
