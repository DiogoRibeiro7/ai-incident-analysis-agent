from __future__ import annotations

import json
from pathlib import Path

from incident_agent.ingestion.metrics import ingest_metrics


def test_ingest_metrics_json_with_mixed_rows(tmp_path: Path) -> None:
    metric_path = tmp_path / "metrics.json"
    payload = {
        "metrics": [
            {
                "timestamp": "2026-03-20T12:00:00Z",
                "service": "api",
                "metric_name": "error_rate",
                "value": 0.12,
                "unit": "ratio",
                "tags": {"route": "/v1/orders"},
            },
            {
                "timestamp": "2026-03-20T12:00:00Z",
                "service": "api",
                "metric_name": "error_rate",
                "value": 0.12,
                "unit": "ratio",
                "tags": {"route": "/v1/orders"},
            },
            {
                "timestamp": "2026-03-20T12:01:00",
                "service": "api",
                "metric_name": "request_latency_ms",
                "value": "512.7",
                "unit": "ms",
                "tags": "{\"route\":\"/v1/orders\"}",
            },
            {
                "timestamp": "2026-03-20T12:02:00Z",
                "service": "api",
                "metric_name": "cpu_usage",
                "value": "bad",
                "unit": "percent",
            },
        ]
    }
    metric_path.write_text(json.dumps(payload), encoding="utf-8")

    result = ingest_metrics(metric_path)

    assert len(result.records) == 2
    assert result.report.total_rows == 4
    assert result.report.valid_rows == 2
    assert result.report.invalid_rows == 1
    assert result.report.dropped_duplicates == 1
    assert result.report.parse_warnings == 1
    assert result.records[1].timestamp.tzinfo is not None


def test_ingest_metrics_csv_invalid_tags_warning(tmp_path: Path) -> None:
    metric_path = tmp_path / "metrics.csv"
    metric_path.write_text(
        "\n".join(
            [
                "timestamp,service,metric_name,value,unit,tags",
                "2026-03-20T12:00:00Z,api,error_rate,0.05,ratio,{bad-json}",
            ]
        ),
        encoding="utf-8",
    )

    result = ingest_metrics(metric_path)

    assert len(result.records) == 1
    assert result.report.parse_warnings == 1
