# Maintainer Triage Playbook

## Purpose

Keep issue and pull request handling consistent as the repository grows.

## Issue Triage Workflow

1. Confirm reproducibility or clarity:
   - If the issue is incomplete, request a minimal repro or exact command/output.
   - If the issue is actionable, keep it open and label it.
2. Apply labels:
   - `bug`: incorrect behavior or regression.
   - `documentation`: docs drift, missing guidance, or broken examples.
   - `enhancement`: incremental improvement.
   - `security`: security-sensitive changes or reports.
   - `release`: release preparation, packaging, and publication tasks.
3. Set milestone:
   - Assign to the nearest planned release when scope is clear.
   - Leave un-milestoned if discovery/refinement is still needed.
4. Determine disposition:
   - Close as `duplicate` if an active canonical issue exists.
   - Close as `not planned` if out of project scope.
   - Keep open if aligned with roadmap and technically feasible.

## Duplicate and Hygiene Rules

- Always link the canonical issue when closing duplicates.
- Prefer merging fragmented discussion into one issue thread.
- Ask reporters to open separate issues for unrelated defects.
- Close stale issues only after requesting missing info and waiting a reasonable period.

## Pull Request Triage Workflow

1. Basic checks:
   - PR description explains what changed and why.
   - CI is green (or failures are unrelated and explained).
   - Scope matches one cohesive concern.
2. Required quality gates:
   - formatting/lint/type checks pass
   - tests pass, including integration where relevant
   - coverage policy remains satisfied
3. Review expectations:
   - Request changes for correctness, safety, regression risk, or missing tests.
   - Prefer explicit file-level comments over vague requests.
4. Merge policy:
   - Use squash merge by default for linear history.
   - Do not merge with unresolved review threads.
   - Do not merge if required checks are failing.

## Closing and Deferring Work

Close an issue/PR when:
- work is completed and validated
- duplicate to canonical tracked work
- clearly out of scope (`not planned`)

Defer when:
- blocked on external dependency or release sequencing
- scope is too broad and must be split into smaller issues

When deferring, leave a concrete next action and owner if possible.

## Maintainer Response Targets

- Initial triage for new issues/PRs: within 3 business days.
- First technical feedback on active PRs: within 5 business days.
- Security-sensitive items: prioritize immediately and follow `SECURITY.md`.
