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

`RootCauseHypothesis.root_cause_support` is a relative support score, not a
calibrated probability. It is calculated as:

```text
root_cause_support = top_candidate_score / sum(candidate_scores)
```

Candidate scores come from severity-ranked evidence plus deterministic service
failure and downstream-impact bonuses. The score is useful for comparing RCA
candidates within the same incident, but it should not be interpreted as
statistical confidence.

Older serialized RCA artifacts containing `confidence_score` are accepted on
input for migration compatibility. New artifacts serialize `root_cause_support`.

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
