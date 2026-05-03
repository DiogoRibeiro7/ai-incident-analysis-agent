# Clean-Clone Command Validation

Last validated: **2026-05-03**

## Scope

Validated from a local clone with project dependencies installed via `poetry install`.

## Commands Verified

- `poetry run incident-agent validate-data --logs data/sample/incident/logs.csv --metrics data/sample/incident/metrics.json`
- `poetry run incident-agent ingest-data --logs data/sample/degraded/logs.jsonl --metrics data/sample/degraded/metrics.csv --output-dir artifacts/ingestion/degraded`
- `poetry run incident-agent run-pipeline --logs data/sample/incident/anomaly_logs.csv --metrics data/sample/incident/anomaly_metrics.csv --artifact-root artifacts/pipeline --bucket-size-minutes 5`
- `poetry run incident-agent list-incidents --artifact-dir <run_dir>`
- `poetry run incident-agent list-reports --artifact-dir <run_dir>`
- `poetry run incident-agent show-report --artifact-dir <run_dir> --index 0`
- `poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.json`
- `poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.md`
- `poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.html`

## Prerequisite-Gated Commands

- Prometheus example requires a reachable Prometheus server at `--prometheus-url`.
- Docker Compose example requires Docker Engine + Compose plugin installed.
- Webhook export commands require a reachable destination URL and may fail against placeholder endpoints.
- `compare-eval` requires an existing candidate summary artifact path.

## Notes

- `run_dir` placeholders in README refer to a generated directory under `artifacts/pipeline/<run_id>/`.
