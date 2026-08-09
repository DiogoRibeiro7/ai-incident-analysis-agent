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
- The default provider mode is `mock`, so local and Docker runs do not require
  external credentials.
- Set `INCIDENT_AGENT_OPENAI_API_KEY` in `.env` only when using
  `llm.provider=openai`. The generic `OPENAI_API_KEY` variable is ignored.
- The API is intended for local or trusted-network use. It does not implement
  end-user authentication. Keep it behind your own access controls before
  exposing it beyond a trusted environment.
- Outbound Prometheus destinations are blocked unless configured in
  `connectors.prometheus.allowed_hosts`. Webhook destinations must exactly match
  `webhook_export.allowed_urls`. Private-network or HTTP destinations require
  explicit opt-in for trusted deployments.

## Published Container Images

Release tags in GitHub (for example `v0.1.0`) trigger image publishing to GHCR:

- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:v0.1.0`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:0.1`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:0`
- `ghcr.io/diogoribeiro7/ai-incident-analysis-agent:sha-<commit>`

Manual publishing is also available through the `container-publish` workflow dispatch.
