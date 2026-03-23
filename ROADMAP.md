# ROADMAP

This file tracks the shorter, reality-based roadmap for the repository. It intentionally reflects implemented work and near-term gaps only.

## Completed

- package scaffold and typed schemas
- CLI and FastAPI entrypoints
- local file ingestion with validation and quality reporting
- timeline normalization and configurable bucket sizes
- deterministic anomaly detection across multiple signal types
- dependency-aware incident correlation
- heuristic RCA artifacts and evidence ranking
- prompt rendering from structured RCA inputs
- mock and OpenAI-backed provider support
- end-to-end pipeline orchestration with persisted artifacts
- operator-focused CLI commands
- evaluation harness and synthetic benchmark generation
- structured observability and fault-tolerant pipeline execution
- report export in JSON, Markdown, and HTML

## Next likely improvements

- retrieval over runbooks and historical incidents
- stronger evidence ranking and output validation policies
- token and cost accounting
- live observability platform connectors
- deployment packaging and production manifests

## Not implemented yet

- CloudWatch connector
- Grafana / Prometheus connector
- Datadog connector
- incident ticket creation integration
- human review workflow
- deployment manifests
