# Anomaly Detection

## Goal

Detect first-pass anomaly candidates from normalized timeline windows using deterministic, explainable statistical rules.

## Module layout

Main package: `src/incident_agent/anomaly_detection/`

- `common.py`: rolling baseline, MAD, z-score logic
- `error_rate.py`
- `latency.py`
- `cpu.py`
- `memory.py`
- `traffic.py`
- `availability.py`
- `engine.py`: orchestration and config loading

## Detection approach

All detectors use:
- rolling median baseline,
- MAD-based robust scale,
- z-score style threshold gating,
- minimum support and relative-change guards.

Detection runs:
- per service,
- globally (`affected_service="global"` with `scope="global"`).

## Output schema

`src/incident_agent/schemas/anomaly.py` defines:
- `AnomalyCandidate`
- `AnomalyDetectionResult`

Each anomaly includes:
- timestamp window,
- anomaly type,
- affected service,
- severity score,
- observed value,
- baseline value,
- evidence summary.

## Config

`configs/default.yaml` now contains:
- `anomaly_detection.error_rate`
- `anomaly_detection.latency`
- `anomaly_detection.cpu`
- `anomaly_detection.memory`
- `anomaly_detection.traffic`
- `anomaly_detection.availability`

Each detector config supports:
- `min_support`
- `lookback_windows`
- `z_threshold`
- `mad_multiplier`
- `min_relative_change`

## CLI

```bash
poetry run incident-agent detect-anomalies \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --bucket-size-minutes 5
```
