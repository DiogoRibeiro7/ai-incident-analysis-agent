from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from incident_agent.connectors.prometheus import fetch_prometheus_metrics
from incident_agent.core.settings import PrometheusConfig

_PUBLIC_TEST_HOST = "93.184.216.34"


class _FakeClient:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"service": "checkout-service"},
                            "values": [[1710932400, "0.12"], [1710932460, "0.18"]],
                        }
                    ],
                },
            },
        )


def test_fetch_prometheus_metrics_parses_query_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("incident_agent.connectors.prometheus.httpx.Client", _FakeClient)
    config = PrometheusConfig(
        enabled=True,
        base_url=f"http://{_PUBLIC_TEST_HOST}:9090",
        step_seconds=60,
        allowed_hosts=[_PUBLIC_TEST_HOST],
        allow_http=True,
        metric_queries={"error_rate": "sum(rate(http_requests_total[5m])) by (service)"},
    )

    points = fetch_prometheus_metrics(
        config=config,
        start_time=datetime(2024, 3, 20, 11, 0, tzinfo=UTC),
        end_time=datetime(2024, 3, 20, 11, 10, tzinfo=UTC),
    )

    assert len(points) == 2
    assert points[0].service == "checkout-service"
    assert points[0].metric_name == "error_rate"
    assert points[0].value == 0.12


def test_fetch_prometheus_metrics_raises_for_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingClient(_FakeClient):
        def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status_code=500, json={"error": "boom"})

    monkeypatch.setattr("incident_agent.connectors.prometheus.httpx.Client", _FailingClient)
    config = PrometheusConfig(
        enabled=True,
        base_url=f"https://{_PUBLIC_TEST_HOST}",
        allowed_hosts=[_PUBLIC_TEST_HOST],
        metric_queries={"latency": "up"},
    )

    with pytest.raises(ValueError):
        fetch_prometheus_metrics(
            config=config,
            start_time=datetime(2024, 3, 20, 11, 0, tzinfo=UTC),
            end_time=datetime(2024, 3, 20, 11, 10, tzinfo=UTC),
        )


def test_fetch_prometheus_metrics_rejects_loopback_url() -> None:
    config = PrometheusConfig(
        enabled=True,
        base_url="http://127.0.0.1:9090",
        allowed_hosts=["127.0.0.1"],
        allow_http=True,
        metric_queries={"latency": "up"},
    )

    with pytest.raises(ValueError, match="disallowed address"):
        fetch_prometheus_metrics(
            config=config,
            start_time=datetime(2024, 3, 20, 11, 0, tzinfo=UTC),
            end_time=datetime(2024, 3, 20, 11, 10, tzinfo=UTC),
        )
