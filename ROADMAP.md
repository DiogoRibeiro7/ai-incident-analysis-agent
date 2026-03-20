# ROADMAP

## Stage 1 — Working local pipeline
- [x] Package scaffold
- [x] Core schemas
- [x] CLI entrypoint
- [x] FastAPI entrypoint
- [x] Mock LLM adapter
- [x] File ingestion parity for local formats (JSONL/CSV logs, CSV/JSON metrics)
- [ ] Stronger incident grouping heuristics
- [ ] Better evidence ranking

## Stage 2 — AI engineering depth
- [ ] Retrieval over runbooks and historical incidents
- [ ] Prompt templates for triage and remediation
- [ ] Real LLM provider adapter
- [ ] Output validation and retry policy
- [ ] Trace and cost observability
- [ ] Evaluation dataset and scorer

## Stage 3 — Production integration
- [ ] CloudWatch connector
- [ ] Grafana / Prometheus connector
- [ ] Datadog connector
- [ ] Ticket creation integration
- [ ] Human review workflow
- [ ] Deployment manifests
