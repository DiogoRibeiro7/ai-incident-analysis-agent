# Roadmap

This roadmap tracks credible future work for the repository. It is intentionally
practical: completed items reflect what is already implemented, and future items
are scoped around the next engineering increments rather than broad product
promises.

## Current State

The repository is a polished portfolio-grade implementation of an incident
analysis workflow for logs and metrics. It has a deterministic local demo,
typed schemas, CLI and API surfaces, release automation, container publishing,
evaluation gates, security hardening, and citation metadata.

Latest release: `v0.2.4`

## Completed Milestones

- Python package scaffold with PEP 621 project metadata.
- CLI and FastAPI entrypoints.
- Local file ingestion with validation and quality reporting.
- Optional Prometheus metrics ingestion through `query_range`.
- Timeline normalization with configurable bucket sizes.
- Deterministic anomaly detection across latency, error rate, CPU, memory,
  traffic, and availability signals.
- Dependency-aware incident correlation.
- Heuristic root-cause analysis artifacts with ranked evidence.
- Structured report generation through mock and OpenAI-backed providers.
- Retrieval over local runbooks, historical incidents, and Grafana annotation
  exports.
- Grounding validation over generated facts and inferences.
- Provider token, latency, and estimated cost accounting.
- End-to-end pipeline orchestration with persisted artifacts.
- Operator-focused CLI commands for inspection, review, export, and delivery.
- Evaluation harness with static and synthetic benchmark scenarios.
- Regression comparison against golden evaluation baselines.
- Structured JSON observability and degraded execution summaries.
- Report export in JSON, Markdown, and HTML.
- Human review workflow for report status transitions.
- Approved-report webhook export with outbound URL policy checks.
- File-path allowlists and configuration security warnings.
- Docker Compose demo packaging and GHCR release images.
- CI quality gates for formatting, linting, typing, tests, coverage, Markdown
  links, evaluation regression, Docker image build, package build, and CodeQL.
- Dependabot security alerts cleared as of `v0.2.4`.
- Repository hygiene files for contribution consistency, citation, conduct,
  support, ownership, pre-commit hooks, and release process.

## Near-Term Improvements

These are the most useful next increments if work resumes.

1. Strengthen evidence ranking.
   - Add richer weighting for time proximity, dependency distance, severity,
     recurrence, and cross-signal agreement.
   - Expand tests with adversarial cases where correlated symptoms should not
     outrank the likely source.

2. Tighten output validation.
   - Add stricter schema checks for final reports before export or webhook
     delivery.
   - Fail or mark degraded when generated claims lack sufficient evidence.
   - Add clearer validation summaries to `run_summary.json`.

3. Improve API ergonomics.
   - Add OpenAPI examples for pipeline and review endpoints.
   - Add pagination or bounded result controls for report, anomaly, and incident
     listing endpoints.
   - Add API-level regression tests for malformed requests and review lifecycle
     edge cases.

4. Expand connector coverage.
   - Add a CloudWatch metrics/logs connector.
   - Add a Datadog metrics/events connector.
   - Add a Grafana live metrics connector to complement existing context
     ingestion docs.

5. Add incident-management integrations.
   - Add Jira or GitHub Issues ticket creation for approved reports.
   - Store outbound delivery metadata alongside the existing webhook audit log.
   - Add dry-run mode for ticket creation.

## Medium-Term Tracks

These are larger workstreams that should be split into multiple PRs.

- Production deployment manifests for Kubernetes or a managed container runtime.
- Auth and authorization around the API for shared environments.
- Persistent storage backend beyond local filesystem artifacts.
- Multi-provider support beyond OpenAI, keeping the existing provider
  abstraction and evaluation modes.
- More realistic benchmark scenarios with noisy, missing, delayed, and
  contradictory signals.
- Report diffing between runs to support incident review and regression
  analysis.
- UI or dashboard for browsing runs, incidents, evidence, and exported reports.

## Maintenance Backlog

- Keep dependencies current through Dependabot and release patched lockfiles
  when security updates affect published artifacts.
- Review GitHub Actions versions on a regular schedule.
- Keep README examples aligned with the latest stable release tag.
- Keep `CITATION.cff` and `.zenodo.json` synchronized with release metadata.
- Periodically run the clean-clone validation workflow documented in
  [clean_clone_validation.md](docs/clean_clone_validation.md).

## Not Implemented

- CloudWatch connector.
- Datadog connector.
- Grafana live metrics connector.
- Ticket creation in Jira, GitHub Issues, Linear, or similar systems.
- Production authentication and authorization.
- Production deployment manifests.
- Persistent database-backed artifact storage.
- Browser-based review dashboard.

## Non-Goals For The Current Version

- Replacing production incident-management platforms.
- Training a learned root-cause model.
- Running unmanaged external network discovery.
- Handling arbitrary untrusted file paths outside configured allowlists.
- Guaranteeing production deployment hardening from the demo container setup.
