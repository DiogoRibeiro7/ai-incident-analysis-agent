# End-to-End Pipeline

## Goal

Run one command that executes:
- ingestion
- normalization
- anomaly detection
- correlation
- RCA
- final report generation

and persists each stage output as inspectable artifacts.

## Orchestrator

Implementation:
- `src/incident_agent/services/pipeline.py`

Result model:
- `src/incident_agent/schemas/pipeline.py`
- `PipelineRunResult`

## CLI usage

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --artifact-root artifacts/pipeline \
  --bucket-size-minutes 5
```

## API usage

Endpoint:
- `POST /analyze-pipeline`

Request fields:
- `logs_path`
- `metrics_path`
- `config_path` (optional)
- `artifact_root` (optional)
- `bucket_size_minutes` (optional)

## Artifact structure

For each run (`<artifact_root>/<run_id>/`):
- `normalized/timeline.json`
- `anomalies/anomalies.json`
- `incidents/incidents.json`
- `rca/rca_hypotheses.json`
- `reports/final_reports.json`

## Sample scenario

Use the bundled scenario:
- logs: `data/sample/incident/anomaly_logs.csv`
- metrics: `data/sample/incident/anomaly_metrics.csv`

This scenario should produce at least one final report in the artifacts directory.

## Runtime observability

Pipeline execution logs machine-readable JSON events for:
- stage start/end/failure
- stage counts
- stage timing (`duration_ms`)
- run-level lifecycle (`pipeline.run.*`)

Provider retries and failures are also logged by the OpenAI adapter.

See `docs/observability.md` for event names and correlation fields.
