# AI Incident Analysis Agent

[![CI](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/ci.yml)
[![CodeQL](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/codeql.yml)
[![Smoke](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml/badge.svg?branch=develop)](https://github.com/DiogoRibeiro7/ai-incident-analysis-agent/actions/workflows/smoke.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Poetry](https://img.shields.io/badge/deps-poetry-informational.svg)](https://python-poetry.org/)

AI engineering project for incident analysis over logs and metrics. The system ingests operational signals, normalizes timelines, detects anomalies, correlates incidents, runs deterministic RCA, and generates grounded summaries.

## Highlights

- End-to-end analysis pipeline with persisted artifacts
- Deterministic anomaly detection and dependency-aware incident correlation
- RCA evidence bundles and ranked root-cause hypotheses
- LLM abstraction (mock + OpenAI) with structured output schemas
- Evaluation harness for benchmark scenarios and mode comparison
- JSON observability logs with run/request IDs, timings, retries, and failures
- FastAPI + CLI interfaces for local runs and demos

## Table of contents

- [Quick start](#quick-start)
- [Main commands](#main-commands)
- [API endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Observability](#observability)
- [Evaluation harness](#evaluation-harness)
- [Repository layout](#repository-layout)
- [Project docs](#project-docs)

## Quick start

### 1. Install dependencies

```bash
poetry install
```

### 2. Run tests

```bash
poetry run pytest
```

### 3. Run full pipeline on sample data

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --artifact-root artifacts/pipeline \
  --bucket-size-minutes 5
```

### 4. Run API locally

```bash
poetry run uvicorn incident_agent.api.main:app --reload
```

## Main commands

### Data validation and ingestion

```bash
poetry run incident-agent validate-data \
  --logs data/sample/incident/logs.csv \
  --metrics data/sample/incident/metrics.json

poetry run incident-agent ingest-data \
  --logs data/sample/degraded/logs.jsonl \
  --metrics data/sample/degraded/metrics.csv \
  --output-dir artifacts/ingestion/degraded
```

Supported formats:
- logs: `.jsonl`, `.csv`
- metrics: `.csv`, `.json`, `.jsonl`

### Stage-by-stage analysis

```bash
poetry run incident-agent normalize-timeline --logs <logs> --metrics <metrics>
poetry run incident-agent detect-anomalies --logs <logs> --metrics <metrics>
poetry run incident-agent correlate-incidents --logs <logs> --metrics <metrics>
poetry run incident-agent run-rca --logs <logs> --metrics <metrics>
```

### Operator commands

```bash
poetry run incident-agent print-config
poetry run incident-agent list-incidents --artifact-dir <run_dir>
poetry run incident-agent show-report --artifact-dir <run_dir> --index 0
poetry run incident-agent export-report --artifact-dir <run_dir> --output-path report.md
```

## API endpoints

Core:
- `GET /health`
- `GET /config`
- `POST /analyze`
- `POST /analyze-pipeline`

Job workflow:
- `POST /analysis-jobs`
- `GET /analysis-jobs/{job_id}/reports`
- `GET /incidents?job_id=<id>`
- `GET /anomalies?job_id=<id>`

## Configuration

Main config file: `configs/default.yaml`

Key sections:
- `llm` for provider/model/retry settings
- `normalization`, `anomaly_detection`, `correlation`, `rca` for analysis logic
- `observability` for logging format and level

OpenAI provider setup:
1. Set `llm.provider: openai`
2. Export `INCIDENT_AGENT_OPENAI_API_KEY=<your_api_key>`

## Observability

Pipeline and provider execution emit machine-readable JSON logs, including:
- `run_id` and `request_id`
- stage lifecycle (`start/completed/failed`)
- event counts and `duration_ms`
- provider attempts, retries, and failures

Example:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv 2> logs.jsonl
```

See `docs/observability.md` for event names and fields.

## Resilience and caching

The pipeline supports:
- bounded provider retries
- disk caching for deterministic LLM calls
- disk caching for intermediate pipeline stages
- degraded execution when logs or metrics are partially missing
- persisted failure summaries in `run_summary.json`

Configuration lives under `resilience` in `configs/default.yaml`.

## Evaluation harness

Run benchmark scenarios and compare modes:

```bash
poetry run incident-agent run-eval \
  --benchmark-path eval/benchmarks/scenarios.json \
  --artifact-root artifacts/eval
```

Default compared modes:
- `heuristic-only`
- `mock-llm`

Optional:
- `--include-real-llm` to include `real-llm` mode

## Synthetic scenarios

The project can generate its own benchmark datasets for:
- latency degradation
- error burst
- dependency cascade
- traffic drop
- resource exhaustion
- multi-service partial outage

Example:

```bash
poetry run incident-agent generate-scenario \
  --scenario-id demo-latency \
  --scenario-type latency_degradation \
  --root-cause-service checkout-service
```

See `eval/benchmarks/synthetic_scenarios.json` and `docs/synthetic_scenarios.md`.

## Repository layout

```text
src/incident_agent/
  agents/            # Agent orchestration
  api/               # FastAPI application
  core/              # Runtime settings
  ingestion/         # Typed file ingestion and quality reports
  normalization/     # Timeline alignment and bucket features
  anomaly_detection/ # Deterministic detectors
  correlation/       # Incident correlation engine
  rca/               # Evidence ranking + root-cause hypotheses
  prompts/           # Prompt templates and renderers
  llm/               # Provider abstraction and adapters
  eval/              # Evaluation harness implementation
  schemas/           # Pydantic contracts
  services/          # End-to-end workflows
  utils/             # Shared utilities (including observability)
configs/             # YAML configuration
data/sample/         # Example datasets
docs/                # Design and usage docs
tests/               # Unit and integration tests
eval/                # Benchmark scenario definitions
```

## Project docs

- `docs/architecture.md`
- `docs/pipeline.md`
- `docs/observability.md`
- `docs/evaluation.md`
- `docs/llm_provider.md`
- `docs/prompting.md`
- `docs/rca.md`
- `docs/synthetic_scenarios.md`
