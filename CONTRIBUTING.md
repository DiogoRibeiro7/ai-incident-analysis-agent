# Contributing

## Local quality gates

Install dependencies:

```bash
poetry install
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

## Maintainer operations

Maintainer issue/PR handling expectations live in
[docs/triage_playbook.md](docs/triage_playbook.md).
