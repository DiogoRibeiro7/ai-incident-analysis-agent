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
- retrieval over runbooks, historical incidents, and Grafana annotation exports
- grounding validation over generated facts and inferences
- mock and OpenAI-backed provider support
- provider token, latency, and estimated cost accounting
- end-to-end pipeline orchestration with persisted artifacts
- operator-focused CLI commands
- evaluation harness and synthetic benchmark generation
- structured observability and fault-tolerant pipeline execution
- report export in JSON, Markdown, and HTML
- human review workflow for report status transitions
- approved-report webhook export with outbound URL policy checks
- Prometheus metrics ingestion through `query_range`
- demo Docker packaging with Compose and GHCR release images
- file-path allowlists and configuration security warnings

## Next likely improvements

- stronger evidence ranking and stricter output validation policies
- additional live observability platform connectors
- production deployment manifests
- ticketing and incident-management integrations
- broader provider support

## Not implemented yet

- CloudWatch connector
- Grafana live metrics connector
- Datadog connector
- incident ticket creation integration
- production deployment manifests
