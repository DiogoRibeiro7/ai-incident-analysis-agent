# AI Incident Analysis Agent

[![CI](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml)
[![CodeQL](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml)
[![Smoke](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Poetry](https://img.shields.io/badge/deps-poetry-informational.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

Incident analysis system for logs and metrics, built as an AI engineering portfolio project. It ingests operational data, normalizes it into aligned time windows, detects anomalies, correlates incident candidates, runs deterministic RCA, and generates structured reports through a provider abstraction.

## Motivation

Most incident response demos jump directly to a model prompt and skip the engineering layers that make incident tooling trustworthy. This project focuses on those layers:
- typed ingestion and validation
- deterministic preprocessing and heuristics
- explicit evidence and RCA artifacts
- provider abstraction and structured outputs
- observability, caching, and degraded execution
- evaluation workflows and synthetic benchmark generation

The result is a repository that demonstrates practical AI systems engineering rather than only prompt design.

## What is implemented

- Local ingestion for logs and metrics with validation and quality reporting
- Timeline normalization into configurable 1, 5, or 15-minute buckets
- Deterministic anomaly detectors for latency, error rate, CPU, memory, traffic, and availability
- Dependency-aware incident correlation
- Root-cause analysis artifacts with ranked evidence and confidence scores
- Prompt rendering from structured RCA context
- Mock and OpenAI provider support
- End-to-end pipeline execution with persisted artifacts
- CLI and FastAPI interfaces
- JSON observability logging with run/request correlation
- Fault-tolerant execution with retries, caches, and degraded-run summaries
- Evaluation harness with static and synthetic benchmark scenarios
- Multi-format report export: JSON, Markdown, and HTML

## Architecture

The system is organized as a layered pipeline:

1. Ingestion loads local files and produces typed `LogEvent` and `MetricPoint` records.
2. Normalization converts timestamps to UTC and aligns logs and metrics into timeline buckets.
3. Anomaly detection applies deterministic rules with rolling baselines and threshold guards.
4. Correlation groups related anomalies into incident candidates using time proximity and service dependency relationships.
5. RCA ranks evidence, summarizes incident features, and proposes a likely root-cause service.
6. Prompt rendering converts RCA artifacts into grounded prompt inputs.
7. Provider execution generates final summaries through a mock or OpenAI backend.
8. Export and delivery expose artifacts through the CLI, API, and file-based reports.

If you want the module-by-module view, start with [architecture.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/architecture.md).

## Data Model

Core records:
- `LogEvent`: normalized application or infrastructure log line
- `MetricPoint`: normalized metric observation
- `TimelineEvent` and `TimelineBucketFeatures`: aligned timeline representations
- `AnomalyCandidate`: first-pass detector output
- `CorrelatedIncidentCandidate`: grouped anomaly cluster with a suspected primary service
- `EvidenceBundle`, `IncidentSummaryFeatures`, `RootCauseHypothesis`: RCA artifacts
- `FinalIncidentReport`: canonical user-facing report schema

The canonical report schema lives in [final_report.py](C:/Users/diogo/work_code/ai-incident-analysis-agent/src/incident_agent/schemas/final_report.py).

## Quick Start

Install dependencies:

```bash
poetry install
```

Run the test suite:

```bash
poetry run pytest
```

Run the full local quality gate:

```bash
make quality
```

Run the full pipeline on sample incident data:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --artifact-root artifacts/pipeline \
  --bucket-size-minutes 5
```

Run the API locally:

```bash
poetry run uvicorn incident_agent.api.main:app --reload
```

## How the Pipeline Works

The default pipeline command performs:
- ingestion
- normalization
- anomaly detection
- incident correlation
- RCA
- final report generation
- artifact persistence

Each run writes a timestamped artifact directory containing:
- `normalized/timeline.json`
- `anomalies/anomalies.json`
- `incidents/incidents.json`
- `rca/rca_hypotheses.json`
- `reports/final_reports.json`
- `run_summary.json`

`run_summary.json` captures warnings, degraded execution state, completed stages, and failure summaries.

## CLI Usage

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

Run stage-by-stage analysis:

```bash
poetry run incident-agent normalize-timeline --logs <logs> --metrics <metrics>
poetry run incident-agent detect-anomalies --logs <logs> --metrics <metrics>
poetry run incident-agent correlate-incidents --logs <logs> --metrics <metrics>
poetry run incident-agent run-rca --logs <logs> --metrics <metrics>
```

Operator commands:

```bash
poetry run incident-agent print-config
poetry run incident-agent list-incidents --artifact-dir <run_dir>
poetry run incident-agent show-report --artifact-dir <run_dir> --index 0
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.json
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.md
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.html
```

Generate synthetic incident scenarios:

```bash
poetry run incident-agent generate-scenario \
  --scenario-id demo-latency \
  --scenario-type latency_degradation \
  --root-cause-service checkout-service
```

Run the evaluation harness:

```bash
poetry run incident-agent run-eval \
  --benchmark-path eval/benchmarks/scenarios.json \
  --artifact-root artifacts/eval
```

Run the recruiter demo path:

```bash
make run-demo
```

## API Usage

Core endpoints:
- `GET /health`
- `GET /config`
- `POST /analyze`
- `POST /analyze-pipeline`

Job-oriented endpoints:
- `POST /analysis-jobs`
- `GET /analysis-jobs/{job_id}/reports`
- `GET /incidents?job_id=<id>`
- `GET /anomalies?job_id=<id>`

Example pipeline request:

```json
{
  "logs_path": "data/sample/incident/anomaly_logs.csv",
  "metrics_path": "data/sample/incident/anomaly_metrics.csv",
  "config_path": "configs/default.yaml",
  "artifact_root": "artifacts/pipeline",
  "bucket_size_minutes": 5
}
```

## Evaluation Overview

The evaluation harness compares:
- `heuristic-only`
- `mock-llm`
- optional `real-llm`

It records:
- root-cause correctness
- impacted service correctness
- factual grounding
- hallucination rate
- report completeness
- latency

Benchmarks can be backed by static files or generated on demand through synthetic scenario definitions.

## Observability, Caching, and Resilience

The project includes:
- structured JSON logs with `run_id` and `request_id`
- bounded provider retries
- disk caching for deterministic LLM calls
- disk caching for intermediate pipeline stages
- degraded execution when one dataset is unavailable

This makes repeated runs safer for demos and easier to debug.

## Limitations

Current limitations are explicit:
- ingestion is local-file based; there are no live observability platform connectors yet
- retrieval over runbooks and incident history is not implemented
- RCA is heuristic, not learned
- OpenAI is the only real provider currently supported
- token accounting and cost reporting are not implemented
- deployment packaging and production infrastructure are not included

## Future Work

Logical next steps for the project are:
- add retrieval over runbooks and historical incidents
- add live connectors for systems like Grafana, CloudWatch, or Datadog
- improve evidence ranking and output validation policies
- add deployment manifests and operational packaging
- extend provider support and richer evaluation metrics

## Repository Layout

```text
src/incident_agent/
  api/               # FastAPI application
  anomaly_detection/ # Deterministic detectors
  correlation/       # Incident correlation engine
  eval/              # Evaluation harness
  export/            # Report serializers
  ingestion/         # Typed ingestion and quality reports
  llm/               # Provider abstraction and adapters
  normalization/     # Timeline alignment and bucket aggregation
  prompts/           # Prompt templates and renderers
  rca/               # Root-cause analysis artifacts and scoring
  schemas/           # Canonical contracts
  services/          # End-to-end workflows
  synthetic/         # Synthetic scenario generation
  utils/             # Shared helpers
configs/             # Runtime configuration
data/sample/         # Example datasets
docs/                # Architecture and usage documentation
eval/                # Benchmark definitions
tests/               # Unit and integration tests
```

## Documentation Index

- [CHANGELOG.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/CHANGELOG.md)
- [CONTRIBUTING.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/CONTRIBUTING.md)
- [LICENSE](C:/Users/diogo/work_code/ai-incident-analysis-agent/LICENSE)
- [architecture.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/architecture.md)
- [ingestion.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/ingestion.md)
- [anomaly_detection.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/anomaly_detection.md)
- [correlation.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/correlation.md)
- [rca.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/rca.md)
- [prompting.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/prompting.md)
- [evaluation.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/evaluation.md)
- [pipeline.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/pipeline.md)
- [release_checklist.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/release_checklist.md)
- [demo_walkthrough.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/demo_walkthrough.md)
- [observability.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/observability.md)
- [synthetic_scenarios.md](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/synthetic_scenarios.md)
- [sample_incident_report.html](C:/Users/diogo/work_code/ai-incident-analysis-agent/docs/sample_incident_report.html)
