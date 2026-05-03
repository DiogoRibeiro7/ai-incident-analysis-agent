# Grafana Context Ingestion

## Goal

Ingest Grafana-compatible annotation exports as retrieval context for incident analysis.

## Supported Input Shape

JSON file with an `annotations` array, or a plain JSON array of annotation objects.

Example record fields:
- `id`
- `dashboardUID` / `dashboardUid`
- `dashboardId`
- `panelId`
- `time`
- `timeEnd`
- `tags` (list of strings)
- `text` (required for ingestion)

## Normalization

Each annotation is transformed into a retrieval chunk preserving metadata:

- `source=grafana-annotation`
- annotation and dashboard identifiers
- panel id and time bounds
- tags
- annotation text

## Usage

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --retrieval-enabled \
  --knowledge-source-paths data/knowledge/runbooks \
  --knowledge-source-paths artifacts/grafana/annotations.json
```

## Failure Behavior

- Entries missing `text` are skipped.
- Malformed JSON files are ignored by retrieval loading (best-effort mode).
