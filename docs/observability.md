# Observability and Tracing

## Goal

Make each analysis run diagnosable using structured, machine-readable logs.

## Configuration

Configured in `configs/default.yaml`:

```yaml
observability:
  log_level: INFO
  json_logs: true
```

Fields:
- `log_level`: standard Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `json_logs`: when `true`, logs are emitted as JSON lines

## Correlation IDs

All major logs include:
- `run_id`: pipeline run identifier
- `request_id`: API request identifier (also returned in `x-request-id`)

## Event Families

Pipeline:
- `pipeline.run.started`
- `pipeline.run.completed`
- `pipeline.run.failed`
- `pipeline.stage.start`
- `pipeline.stage.completed`
- `pipeline.stage.failed`
- `pipeline.stage.counts`

Provider (OpenAI):
- `provider.call.start`
- `provider.call.completed`
- `provider.call.failed`
- `provider.request.attempt`
- `provider.request.retry`
- `provider.request.succeeded`
- `provider.request.failed`

API:
- `api.request.started`
- `api.request.completed`
- `api.request.failed`

## Span Timing

Lightweight execution spans are implemented with `execution_span(...)` in:
- `src/incident_agent/utils/observability.py`

Each span emits start/end events and `duration_ms`. Failures emit an error event with `error_type` and `error`.
