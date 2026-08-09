# Incident Correlation

## Goal

Group anomaly candidates into coherent incident candidates and rank the most likely primary service.

## Components

- `src/incident_agent/correlation/engine.py`
- `src/incident_agent/correlation/graph.py`
- `src/incident_agent/services/correlate.py`
- `src/incident_agent/schemas/incident.py`

## Correlation scoring

Anomalies are grouped with an explicit relationship score. The score combines:
- temporal proximity within `max_time_distance_minutes`,
- same-service evidence,
- dependency-graph evidence,
- cross-signal agreement on the same service,
- same anomaly family.

Same-family evidence is intentionally weak and cannot group two anomalies by
itself. A new anomaly needs a local relationship score at or above
`relationship_threshold` before it can join a cluster. Larger multi-service
clusters also require same-service continuity, direct dependency coverage, or
cross-signal support. This keeps close, well-supported cascades together while
preventing broad transitive chains from turning loosely related events into one
large incident.

Clusters with fewer than `minimum_evidence_count` are dropped.

## Dependency-aware root ranking

For each cluster:
- base service score is sum of anomaly severity weighted by anomaly type,
- score is increased when impacted downstream services exist,
- score is decreased when impacted upstream services exist.

Top score becomes `suspected_primary_service`.

## Config

`configs/default.yaml` includes a `correlation` section for:
- `max_time_distance_minutes`
- `minimum_evidence_count`
- `relationship_threshold`
- `temporal_weight`
- `same_service_weight`
- `dependency_weight`
- `cross_signal_weight`
- `same_family_weight`
- `severity_weighting`
- `dependency_downstream_bonus`
- `dependency_upstream_penalty`
- `cross_signal_bonus`
- `same_service_bonus`
- `dependency_graph_path`

Dependency graph example:
- `configs/service_dependencies.yaml`

## CLI

```bash
poetry run incident-agent correlate-incidents \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --bucket-size-minutes 5
```
