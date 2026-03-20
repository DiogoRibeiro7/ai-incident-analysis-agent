# AI Incident Analysis Agent

An AI engineering portfolio project that ingests logs and metrics, detects suspicious incidents, retrieves relevant operational context, and produces grounded incident summaries with suggested next actions.

## What this project demonstrates

- Log and metric ingestion pipelines
- Timeline normalization and configurable time-bucket alignment
- Deterministic anomaly detection (service-level and global)
- Incident enrichment and retrieval over operational context
- LLM-based triage and summarisation with structured outputs
- Guardrails and validation for agent responses
- FastAPI service for analysis requests
- CLI for local experimentation
- Evaluation-oriented design with fixtures and deterministic tests
- Production-minded repository structure

## Planned workflow

1. Ingest logs and metrics from files, APIs, or observability backends.
2. Normalise raw events into a common schema.
3. Group related anomalies into candidate incidents.
4. Retrieve supporting evidence around the incident window.
5. Build a grounded prompt with explicit evidence snippets.
6. Generate a structured incident report.
7. Validate the output schema and persist the result.

## Repository layout

```text
src/incident_agent/
  agents/         # Agent orchestration
  analysis/       # Incident correlation, feature extraction, heuristics
  api/            # FastAPI application
  clients/        # External connectors (future)
  core/           # Settings and constants
  ingest/         # Parsers and normalisation
  ingestion/      # Typed local ingestion (files + quality report)
  llm/            # LLM interfaces and adapters
  normalization/  # Timeline alignment and bucket feature extraction
  anomaly_detection/ # Rule-based anomaly detectors
  prompts/        # Prompt builders and templates
  schemas/        # Pydantic models
  services/       # End-to-end use cases
  utils/          # Shared helpers
configs/          # YAML configuration
data/sample/      # Small local examples
tests/            # Unit and integration tests
```

## Quick start

### 1. Install dependencies

```bash
poetry install
```

### 2. Run the CLI demo

```bash
poetry run incident-agent \
  analyze \
  --logs data/sample/logs.jsonl \
  --metrics data/sample/metrics.jsonl
```

### 3. Validate and ingest datasets

```bash
poetry run incident-agent validate-data \
  --logs data/sample/incident/logs.csv \
  --metrics data/sample/incident/metrics.json

poetry run incident-agent ingest-data \
  --logs data/sample/degraded/logs.jsonl \
  --metrics data/sample/degraded/metrics.csv \
  --output-dir artifacts/ingestion/degraded
```

Supported file formats:
- logs: `.jsonl`, `.csv`
- metrics: `.csv`, `.json`, `.jsonl`

### 4. Run the API locally

```bash
poetry run uvicorn incident_agent.api.main:app --reload
```

### 5. Run tests

```bash
poetry run pytest
```

### 6. Normalize timeline windows

```bash
poetry run incident-agent normalize-timeline \
  --logs data/sample/incident/logs.csv \
  --metrics data/sample/incident/metrics.json \
  --bucket-size-minutes 5
```

### 7. Detect anomaly candidates

```bash
poetry run incident-agent detect-anomalies \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --bucket-size-minutes 5
```

## Example use cases

- Database latency spikes correlated with application errors
- API outage triage using logs, saturation metrics, and deployment metadata
- Authentication failure surges linked to upstream provider instability
- Flink or stream-processing lag analysis with evidence-based summaries

## Initial scope

The scaffold currently includes:

- a clean package structure
- schemas for logs, metrics, incidents, and reports
- a simple correlation pipeline
- a mock LLM adapter for deterministic local development
- a CLI entrypoint
- a FastAPI endpoint
- starter tests

## Near-term roadmap

### Stage 1

- complete file and API ingestion connectors
- implement rule-based incident grouping
- improve evidence selection around the incident window
- add prompt templates for triage, root-cause hypotheses, and remediation

### Stage 2

- add vector retrieval over runbooks and incident history
- support real LLM backends
- add evaluation fixtures and scoring scripts
- add tracing, token accounting, and latency reporting

### Stage 3

- integrate with Grafana, CloudWatch, Datadog, or OpenSearch
- add human-in-the-loop review flows
- add alerting and incident ticket creation
- support multi-agent workflows for deep diagnosis
