# Root-Cause Analysis (RCA)

## Goal

Produce explicit, testable root-cause artifacts from correlated incidents without relying on LLM prompting.

## Design

RCA is split into modular components under `src/incident_agent/rca/`:
- `evidence.py`: evidence ranking and contributing signal extraction
- `summarize.py`: incident feature summarization
- `dependency.py`: dependency-aware downstream impact reasoning
- `scoring.py`: root-cause candidate scoring and ambiguity detection
- `engine.py`: orchestration and config loading

This keeps reasoning independent from prompt templates, making it easy to replace heuristics later with model-assisted strategies.

## Intermediate artifacts

Defined in `src/incident_agent/schemas/rca.py`:
- `EvidenceBundle`
- `IncidentSummaryFeatures`
- `RootCauseHypothesis`
- `RCAResult`

## Config

`configs/default.yaml` includes:
- `rca.service_failure_bonus`
- `rca.downstream_bonus`
- `rca.ambiguity_delta`
- `rca.dependency_graph_path`

## CLI

```bash
poetry run incident-agent run-rca \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --bucket-size-minutes 5
```
