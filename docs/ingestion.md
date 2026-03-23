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
- `src/incident_agent/ingest/files.py`

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

Generated files include:
- `normalized_logs.jsonl`
- `normalized_metrics.jsonl`
- `ingestion_report.json`
