# Ingestion

## Goal

Load logs and metrics from local files, validate them, and normalize them into typed records the rest of the pipeline can consume.

## Supported formats

Logs:
- `.jsonl`
- `.csv`

Metrics:
- `.csv`
- `.json`
- `.jsonl`

## Main modules

- `src/incident_agent/ingestion/logs.py`
- `src/incident_agent/ingestion/metrics.py`
- `src/incident_agent/ingestion/common.py`
- `src/incident_agent/ingestion/__init__.py` (canonical public entrypoint)

## Validation behavior

The ingestion layer:
- parses timestamps into UTC
- validates required fields
- normalizes types
- drops exact duplicates
- tracks warnings and invalid rows through `DataQualityReport`

Invalid rows do not crash ingestion by default. They are counted and surfaced in the quality report.

## Output models

Defined in `src/incident_agent/schemas/events.py`:
- `LogEvent`
- `MetricPoint`

Quality reporting is implemented through:
- `IngestionResult`
- `DataQualityReport`

## CLI

Validate datasets:

```bash
poetry run incident-agent validate-data \
  --logs data/sample/incident/logs.csv \
  --metrics data/sample/incident/metrics.json
```

Persist normalized ingestion artifacts:

```bash
poetry run incident-agent ingest-data \
  --logs data/sample/degraded/logs.jsonl \
  --metrics data/sample/degraded/metrics.csv \
  --output-dir artifacts/ingestion/degraded
```

## Prometheus connector

Pipeline execution can pull metrics from Prometheus via `query_range`:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics unused.csv \
  --metrics-source prometheus \
  --prometheus-url http://localhost:9090 \
  --prometheus-query error_rate='sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)'
```

Connector defaults live in `configs/default.yaml` under:
- `connectors.prometheus.base_url`
- `connectors.prometheus.timeout_seconds`
- `connectors.prometheus.step_seconds`
- `connectors.prometheus.metric_queries`

Generated files include:
- `normalized_logs.jsonl`
- `normalized_metrics.jsonl`
- `ingestion_report.json`
