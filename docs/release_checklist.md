# Release Checklist

Use this checklist before publishing a public release or major portfolio update.

## Quality

- `poetry run ruff format --check .`
- `poetry run ruff check .`
- `poetry run mypy src tests`
- `poetry run pytest`
- confirm coverage stays above the enforced threshold

## Packaging

- `poetry build`
- verify the CLI entrypoint works from a clean environment
- verify `incident-agent run-demo` works from a clean clone after `poetry install`

## Documentation

- README matches the current implementation
- roadmap reflects reality, not aspiration
- sample HTML report matches current export styling
- demo walkthrough still points to valid commands and paths
- changelog is updated

## Repository presentation

- license is present
- badges are current
- issue templates and workflows are still valid
- no generated coverage or local artifacts are staged for commit

## Security Signoff

- verify file-path inputs stay within configured security allowlists
- verify config inspection reports no unresolved plaintext secret warnings
- verify API rejects path traversal and disallowed input paths
- confirm release approver records explicit security signoff in release notes

## Demo sanity check

- run `make run-demo`
- verify generated outputs:
  - anomaly artifacts
  - incident artifacts
  - RCA artifacts
  - Markdown report
  - HTML report
  - demo manifest
