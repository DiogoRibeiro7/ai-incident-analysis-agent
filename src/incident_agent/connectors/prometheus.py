"""Prometheus metrics connector."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from incident_agent.core.settings import PrometheusConfig
from incident_agent.schemas.events import MetricPoint
from incident_agent.utils.security import validate_outbound_url


def fetch_prometheus_metrics(
    *,
    config: PrometheusConfig,
    start_time: datetime,
    end_time: datetime,
) -> list[MetricPoint]:
    """Fetch metric points from Prometheus query_range endpoints."""

    if not config.metric_queries:
        return []

    base_url = config.base_url.rstrip("/")
    endpoint = validate_outbound_url(
        f"{base_url}/api/v1/query_range",
        allowed_hosts=config.allowed_hosts,
        allowed_schemes={"http", "https"} if config.allow_http else {"https"},
        allow_private_networks=config.allow_private_networks,
    )
    points: list[MetricPoint] = []

    for metric_name, query in sorted(config.metric_queries.items()):
        params = {
            "query": query,
            "start": start_time.astimezone(UTC).isoformat(),
            "end": end_time.astimezone(UTC).isoformat(),
            "step": str(config.step_seconds),
        }
        with httpx.Client(timeout=config.timeout_seconds, follow_redirects=False) as client:
            response = client.get(endpoint, params=params)

        if 300 <= response.status_code < 400:
            raise ValueError(
                f"Prometheus query_range redirect blocked for metric '{metric_name}' "
                f"with status {response.status_code}."
            )
        if response.status_code >= 400:
            raise ValueError(
                f"Prometheus query_range failed for metric '{metric_name}' "
                f"with status {response.status_code}."
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Prometheus response must be a JSON object.")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Prometheus response missing 'data' object.")

        result = data.get("result")
        if not isinstance(result, list):
            raise ValueError("Prometheus response 'data.result' must be a list.")

        for series in result:
            if not isinstance(series, dict):
                continue
            metric_labels = series.get("metric")
            if not isinstance(metric_labels, dict):
                continue
            values = series.get("values")
            if not isinstance(values, list):
                continue

            service = _select_service(metric_labels)
            tags = {
                str(key): str(value)
                for key, value in metric_labels.items()
                if key not in {"service", "job", "instance"}
            }
            for row in values:
                point = _parse_value_row(
                    row=row,
                    service=service,
                    metric_name=metric_name,
                    tags=tags,
                )
                if point is not None:
                    points.append(point)

    points.sort(key=lambda item: (item.timestamp, item.service, item.metric_name))
    return points


def _select_service(labels: dict[str, object]) -> str:
    for key in ("service", "job", "instance"):
        value = labels.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "prometheus-unknown"


def _parse_value_row(
    *,
    row: object,
    service: str,
    metric_name: str,
    tags: dict[str, str],
) -> MetricPoint | None:
    if not isinstance(row, list) or len(row) != 2:
        return None

    raw_timestamp, raw_value = row
    if not isinstance(raw_timestamp, int | float):
        return None
    if not isinstance(raw_value, str):
        return None

    try:
        value = float(raw_value)
    except ValueError:
        return None

    timestamp = datetime.fromtimestamp(float(raw_timestamp), tz=UTC)
    return MetricPoint(
        timestamp=timestamp,
        service=service,
        metric_name=metric_name,
        value=value,
        unit=None,
        tags=tags,
    )
