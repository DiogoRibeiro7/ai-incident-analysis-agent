# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on Keep a Changelog and uses repository-focused release notes.

## [0.2.4] - 2026-08-09

### Fixed

- Refreshed vulnerable transitive dependencies in the lockfile by updating `idna` to 3.18 and `Pygments` to 2.20.0.

## [0.2.3] - 2026-08-09

### Fixed

- Docker builds now copy project packaging inputs before installing the package inside the image.

## [0.2.2] - 2026-08-09

### Fixed

- Container builds now use Poetry 2.2.1 so PEP 621 project metadata is accepted during image publication.

## [0.2.1] - 2026-08-09

### Added

- Repository professionalism files for contribution consistency, citation, support, conduct, ownership, and pull-request review.

### Changed

- README rewritten around a clearer project pitch, quick-start path, workflow guide, quality gates, and documentation index.
- Project metadata moved to modern PEP 621 configuration.
- Release, citation, Zenodo, and package metadata synchronized.

## [0.2.0] - 2026-08-09

### Added

- Zenodo metadata for citation and archival workflows.
- Claim-level grounding validation with citation support and evaluation metrics.
- Expanded deterministic benchmark corpus with labeled incident, service, and anomaly expectations.
- Regression coverage for evaluation modes, grounding, retrieval path policy, SSRF handling, normalization semantics, correlation, RCA schema compatibility, environment samples, and Markdown links.
- Docker/local environment example validation and explicit Docker provider defaults.

### Changed

- Default branch renamed to `main`.
- Documentation synchronized with implemented Prometheus ingestion, retrieval, review workflow, webhook export, deployment packaging, and security assumptions.
- RCA support score terminology now uses `root_cause_support` while accepting legacy serialized inputs.

### Fixed

- Evaluation comparison now detects missing or unexpected modes.
- Retrieval path validation rejects traversal and symlink escapes outside configured allowlists.
- Outbound URL validation blocks private, loopback, link-local, metadata-service, and redirect destinations unless explicitly trusted.
- Error-rate metrics and error-log counts remain separate signal units.
- Missing metric buckets use explicit zero, unavailable, or unknown semantics.
- Correlation avoids grouping unrelated same-family anomalies and weak dependency chains.
- OpenAI provider configuration uses the repository-specific key consistently.
- Repository Markdown links no longer point to machine-local paths.

## [0.1.0] - 2026-03-23

### Added

- local log and metric ingestion with validation and typed normalization
- timeline bucketing and deterministic anomaly detectors
- dependency-aware incident correlation and heuristic RCA artifacts
- prompt rendering from RCA context
- mock and OpenAI provider support
- end-to-end pipeline orchestration with persisted artifacts
- structured observability, retries, caching, and degraded execution summaries
- evaluation harness with synthetic benchmark generation
- report export in JSON, Markdown, and HTML
- deterministic recruiter demo path
- CI quality gates and coverage enforcement

### Documentation

- portfolio-oriented README
- ingestion, evaluation, synthetic scenario, and demo walkthrough docs
- release checklist

### Release

- first polished public release candidate
