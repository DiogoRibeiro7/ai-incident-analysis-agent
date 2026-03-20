# Incident Correlation

## Goal

Group anomaly candidates into coherent incident candidates and rank the most likely primary service.

## Components

- `src/incident_agent/correlation/engine.py`
- `src/incident_agent/correlation/graph.py`
- `src/incident_agent/services/correlate.py`
- `src/incident_agent/schemas/incident.py`

## Correlation rules

Anomalies are grouped when they are:
- close in time (`max_time_distance_minutes`),
- and related by at least one condition:
  - same service,
  - dependency relationship,
  - same anomaly family,
  - cross-signal agreement on the same service.

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
