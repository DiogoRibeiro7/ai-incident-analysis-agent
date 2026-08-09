# Contributing

## Local quality gates

Install dependencies:

```bash
poetry install
```

Install local commit hooks:

```bash
poetry run pre-commit install
```

Run the same checks enforced in CI:

```bash
make quality
```

Available local targets:
- `make format-check`
- `make lint`
- `make typecheck`
- `make test-unit`
- `make test-integration`
- `make coverage`
- `make quality`

Run all pre-commit hooks manually:

```bash
poetry run pre-commit run --all-files
```

## Coverage policy

The repository enforces:
- branch-aware coverage measurement
- `coverage.xml` generation
- minimum total coverage of `85%`

The default `pytest` configuration already includes the coverage gate, so running `poetry run pytest` locally matches CI behavior.

## CI expectations

CI currently fails on:
- formatting drift
- lint violations
- mypy failures
- test failures
- coverage dropping below the enforced threshold
- unresolved Markdown links
- evaluation regression-gate failures
- container image build failures

## Pull request expectations

Before opening a PR:

- keep the change focused and avoid unrelated refactors;
- update tests when behavior changes;
- update documentation and changelog entries for user-facing changes;
- run `make quality`;
- include validation evidence in the PR template.

Security-sensitive changes should call out affected trust boundaries, file-path
policy, outbound-network policy, or credential-handling behavior.

## Maintainer operations

Maintainer issue/PR handling expectations live in
[docs/triage_playbook.md](docs/triage_playbook.md).
