# Timeline Normalization

## Goal

The normalization layer aligns logs and metrics on a shared UTC timeline so downstream anomaly detection and correlation can operate on deterministic bucketed features.

## Implementation

Main module: `src/incident_agent/normalization/timeline.py`

It provides:
- `load_normalization_config(...)`: loads bucketing and signal config from YAML.
- `align_events_to_timeline(...)`: converts events to UTC, buckets them, and computes per-bucket features.

Config model:
- `bucket_size_minutes`: supports `1`, `5`, `15`
- `log_spike_threshold`
- `error_burst_threshold`
- metric category mappings:
  - `latency_metrics`
  - `cpu_metrics`
  - `memory_metrics`
  - `http_error_rate_metrics`
  - `service_failure_metrics`
  - `metric_missing_policies`

HTTP error-rate metrics and log severity counts stay in separate units. Error-rate metrics are
aggregated as ratios, while ERROR and CRITICAL logs are counted separately.

Normalization builds an explicit bucket grid across the analysis window. Expected-but-absent
metrics use configured missing semantics:
- `zero`: emit a synthetic zero value, used for request-count style traffic metrics.
- `missing`: emit an explicit unknown entry with no numeric value, used for CPU and latency.
- `unavailable`: emit an unavailable signal, used for heartbeat-style metrics.

## Unified timeline representation

Schema file: `src/incident_agent/schemas/timeline.py`

- `TimelineEvent`: normalized event with `bucket_start`, `source`, and signal family.
- `TimelineBucketFeatures`: aggregated metrics for each bucket.
- `TimelineAlignmentResult`: ordered events + ordered bucket features.

## Derived bucket features

For each bucket, the pipeline computes:
- `error_count`
- `synthetic_event_count`
- `error_log_count`
- `critical_log_count`
- `warn_count`
- `unique_services_affected`
- `zero_filled_metric_count`
- `unavailable_missing_metric_count`
- `unknown_missing_metric_count`
- `http_error_rate`
- `p95_latency`
- `cpu_mean` / `cpu_max`
- `memory_mean` / `memory_max`
- `log_spike` (threshold-based)
- `error_burst` (threshold-based)
- `service_failure_signals`

## CLI usage

```bash
poetry run incident-agent normalize-timeline \
  --logs data/sample/incident/logs.csv \
  --metrics data/sample/incident/metrics.json \
  --bucket-size-minutes 5
```

The command prints JSON with:
- `events`: normalized ordered events
- `buckets`: aligned aggregated bucket features
