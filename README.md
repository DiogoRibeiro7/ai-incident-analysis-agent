# AI Incident Analysis Agent

[![CI](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml)
[![CodeQL](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml)
[![Smoke](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml/badge.svg?branch=main)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Poetry](https://img.shields.io/badge/deps-poetry-informational.svg)](https://python-poetry.org/)
[![Release](https://img.shields.io/github/v/release/DiogoRibeiro7/ai-incident-analysis-agent)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

An incident-analysis system for logs and metrics that demonstrates practical AI
systems engineering: typed ingestion, deterministic anomaly detection,
dependency-aware correlation, root-cause evidence ranking, grounded report
generation, evaluation gates, and operational hardening.

The project is designed to be understandable from a clean clone, runnable without
external services, and extensible toward real observability backends.

## At a Glance

| Area | What is included |
| --- | --- |
| Inputs | CSV, JSON, JSONL logs and metrics; optional Prometheus `query_range` metrics |
| Analysis | Timeline normalization, anomaly detection, incident correlation, RCA scoring |
| Generation | Mock provider by default; optional OpenAI provider; grounded context injection |
| Outputs | JSON artifacts, Markdown reports, HTML reports, webhook delivery audit logs |
| Interfaces | Typer CLI, FastAPI service, Docker Compose entrypoint |
| Quality | pytest coverage gate, ruff, mypy strict mode, CodeQL, dependency review |
| Evaluation | Static and synthetic benchmarks with regression comparison artifacts |

## Why This Exists

Most incident-response demos skip the layers that make generated analysis
trustworthy. This repository focuses on those layers first:

- deterministic preprocessing before model calls
- explicit schemas for every pipeline contract
- cited grounding from runbooks and prior incidents
- degraded execution when data or providers are unavailable
- repeatable evaluation and regression checks
- auditable artifacts for review, export, and delivery

The result is a portfolio-grade repository that shows how an AI-assisted
operations workflow can be engineered, tested, and inspected.

## Quick Start

Requirements:

- Python 3.12
- Poetry
- Make, optional but recommended
- Docker Engine and Compose plugin, optional

Install dependencies and run the full quality gate:

```bash
poetry install
make quality
```

Run the deterministic demo:

```bash
make run-demo
```

The demo writes a complete run under:

```text
artifacts/demo/portfolio-demo/
```

Open these outputs first:

- `incident_report.md`
- `incident_report.html`
- `artifacts/run_summary.json`
- `artifacts/reports/final_reports.json`

The walkthrough in [demo_walkthrough.md](docs/demo_walkthrough.md) explains the
scenario and artifact layout.

## Run the Pipeline

Run the bundled sample incident through the complete pipeline:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --artifact-root artifacts/pipeline \
  --bucket-size-minutes 5
```

Enable retrieval from local runbooks and historical incidents:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --retrieval-enabled \
  --knowledge-source-paths data/knowledge/runbooks \
  --knowledge-source-paths data/knowledge/incidents
```

Use Prometheus for metrics:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics unused.csv \
  --metrics-source prometheus \
  --prometheus-url http://localhost:9090 \
  --prometheus-query error_rate='sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)'
```

The Prometheus command requires a reachable Prometheus server. Local-file runs
work without external services.

## Pipeline Stages

The default pipeline performs:

1. Ingest logs and metrics into typed records.
2. Normalize timestamps to UTC and align data into timeline buckets.
3. Detect latency, error-rate, CPU, memory, traffic, and availability anomalies.
4. Correlate related anomalies into incident candidates.
5. Rank evidence and produce root-cause hypotheses.
6. Render grounded analysis inputs from structured context.
7. Generate final reports through the configured provider.
8. Persist artifacts for review, export, and delivery.

Each run writes a timestamped artifact directory containing:

```text
normalized/timeline.json
anomalies/anomalies.json
incidents/incidents.json
rca/rca_hypotheses.json
grounding/grounding_summary.json
reports/final_reports.json
run_summary.json
```

`run_summary.json` captures completed stages, warnings, degraded execution state,
and failure summaries.

## CLI

Validate input data:

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

Run individual analysis stages:

```bash
poetry run incident-agent normalize-timeline --logs <logs> --metrics <metrics>
poetry run incident-agent detect-anomalies --logs <logs> --metrics <metrics>
poetry run incident-agent correlate-incidents --logs <logs> --metrics <metrics>
poetry run incident-agent run-rca --logs <logs> --metrics <metrics>
```

Inspect, review, and export reports:

```bash
poetry run incident-agent print-config
poetry run incident-agent list-incidents --artifact-dir <run_dir>
poetry run incident-agent list-reports --artifact-dir <run_dir>
poetry run incident-agent list-reports --artifact-dir <run_dir> --review-status approved
poetry run incident-agent show-report --artifact-dir <run_dir> --index 0
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.json
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.md
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.html
```

Manage report review state and delivery:

```bash
poetry run incident-agent mark-reviewed --artifact-dir <run_dir> --incident-id <id> --reviewer <name> --note "triage complete"
poetry run incident-agent approve-report --artifact-dir <run_dir> --incident-id <id> --reviewer <name> --note "approved"
poetry run incident-agent reject-report --artifact-dir <run_dir> --incident-id <id> --reviewer <name> --note "needs rework"
poetry run incident-agent export-approved-webhook --artifact-dir <run_dir> --incident-id <id> --destination-url https://example.test/webhook
```

Generate synthetic scenarios and run evaluations:

```bash
poetry run incident-agent generate-scenario \
  --scenario-id demo-latency \
  --scenario-type latency_degradation \
  --root-cause-service checkout-service

poetry run incident-agent run-eval \
  --benchmark-path eval/benchmarks/scenarios.json \
  --artifact-root artifacts/eval

poetry run incident-agent compare-eval \
  --baseline-summary-path eval/golden/baseline_summary.json \
  --candidate-summary-path artifacts/eval/<run_id>/summary.json \
  --output-dir artifacts/eval/compare
```

## API

Run the API locally:

```bash
poetry run uvicorn incident_agent.api.main:app --reload
```

Core endpoints:

- `GET /health`
- `GET /config`
- `POST /analyze`
- `POST /analyze-pipeline`

Job-oriented endpoints:

- `POST /analysis-jobs`
- `GET /analysis-jobs/{job_id}/reports`
- `GET /analysis-jobs/{job_id}/reports?review_status=approved`
- `POST /analysis-jobs/{job_id}/reports/{incident_id}/review`
- `POST /analysis-jobs/{job_id}/reports/{incident_id}/export-webhook`
- `GET /incidents?job_id=<id>`
- `GET /anomalies?job_id=<id>`

Example pipeline request:

```json
{
  "logs_path": "data/sample/incident/anomaly_logs.csv",
  "metrics_path": "data/sample/incident/anomaly_metrics.csv",
  "config_path": "configs/default.yaml",
  "artifact_root": "artifacts/pipeline",
  "bucket_size_minutes": 5,
  "metrics_source": "prometheus",
  "prometheus_url": "http://localhost:9090",
  "prometheus_queries": {
    "error_rate": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) by (service)"
  }
}
```

## Docker

Run the service with Docker Compose:

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

Tagged releases publish container images to GitHub Container Registry:

- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:v<major>.<minor>.<patch>`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:<major>.<minor>`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:<major>`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:sha-<commit>`

Example:

```bash
docker pull ghcr.io/diogoribeiro7/ai-incident-analysis-agent:v0.2.4
```

## Configuration

The default runtime configuration lives in [default.yaml](configs/default.yaml).
Container defaults live in [.env.example](.env.example).

The project runs with a mock provider by default, so local demos do not need API
credentials. To use the OpenAI provider, configure the provider setting and set
`INCIDENT_AGENT_OPENAI_API_KEY`.

## Evaluation

The evaluation harness compares these modes:

- `heuristic-only`
- `mock-llm-no-retrieval`
- `mock-llm-retrieval`
- optional `real-llm-no-retrieval`
- optional `real-llm-retrieval`

It records root-cause correctness, impacted-service correctness, factual
grounding, hallucination rate, report completeness, and latency. Benchmarks can
use static scenarios or synthetic scenario definitions.

See [evaluation.md](docs/evaluation.md) and
[synthetic_scenarios.md](docs/synthetic_scenarios.md) for details.

## Quality and Release Hygiene

Local quality gate:

```bash
make quality
```

Equivalent commands:

```bash
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src tests
poetry run pytest
```

Pre-commit hooks:

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

Release and maintenance process:

- [release_checklist.md](docs/release_checklist.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## Repository Layout

```text
src/incident_agent/
  api/               FastAPI application
  anomaly_detection/ Deterministic detectors
  connectors/        External data-source adapters
  correlation/       Incident grouping and dependency graph logic
  eval/              Evaluation runner and benchmark support
  export/            Report serializers and webhook delivery
  grounding/         Factuality and citation checks
  ingestion/         Typed log and metric ingestion
  knowledge/         Runbook and historical-incident retrieval
  llm/               Provider abstraction and adapters
  normalization/     Timeline alignment and bucket aggregation
  prompts/           Template rendering
  rca/               Root-cause evidence and scoring
  schemas/           Canonical contracts
  services/          End-to-end workflows
  storage/           Artifact storage backends
  synthetic/         Scenario generation
  utils/             Shared operational helpers

configs/             Runtime configuration
data/sample/         Example datasets
docs/                Architecture and usage documentation
eval/                Benchmark definitions and golden baselines
tests/               Unit and integration tests
```

## Limitations

- Log ingestion is local-file based.
- Metrics can come from local files or Prometheus.
- CloudWatch, Datadog, and Grafana live metrics connectors are not included.
- RCA is heuristic and evidence-ranked, not learned.
- OpenAI is the only real provider currently supported.
- Packaging is demo-oriented; production deployment hardening is intentionally
  out of scope for this version.

## Documentation Index

- [architecture.md](docs/architecture.md)
- [artifact_storage.md](docs/artifact_storage.md)
- [clean_clone_validation.md](docs/clean_clone_validation.md)
- [correlation.md](docs/correlation.md)
- [demo_walkthrough.md](docs/demo_walkthrough.md)
- [deployment.md](docs/deployment.md)
- [evaluation.md](docs/evaluation.md)
- [grafana_context_ingestion.md](docs/grafana_context_ingestion.md)
- [historical_incident_corpus.md](docs/historical_incident_corpus.md)
- [ingestion.md](docs/ingestion.md)
- [llm_provider.md](docs/llm_provider.md)
- [normalization.md](docs/normalization.md)
- [observability.md](docs/observability.md)
- [pipeline.md](docs/pipeline.md)
- [prompting.md](docs/prompting.md)
- [rca.md](docs/rca.md)
- [release_checklist.md](docs/release_checklist.md)
- [ROADMAP.md](ROADMAP.md)
- [runbook_ingestion.md](docs/runbook_ingestion.md)
- [sample_incident_report.html](docs/sample_incident_report.html)
- [synthetic_scenarios.md](docs/synthetic_scenarios.md)
- [triage_playbook.md](docs/triage_playbook.md)
- [CHANGELOG.md](CHANGELOG.md)
- [CITATION.cff](CITATION.cff)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [LICENSE](LICENSE)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)
