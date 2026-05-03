# Deployment Packaging

## Goal

Provide a reproducible demo deployment path for the API with persistent artifacts.

## Files

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`

## Quickstart

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Start API container:

```bash
docker compose up --build
```

3. Verify health:

```bash
curl http://localhost:8000/health
```

4. Run one sample pipeline request:

```bash
curl -X POST http://localhost:8000/analyze-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "logs_path":"data/sample/incident/anomaly_logs.csv",
    "metrics_path":"data/sample/incident/anomaly_metrics.csv",
    "artifact_root":"artifacts/pipeline",
    "bucket_size_minutes":5
  }'
```

## Notes

- Artifacts are persisted on host at `./artifacts`.
- Config and data are mounted read-only from `./configs` and `./data`.
- API container exposes port `8000` by default (`API_PORT` in `.env`).
