# Demo Walkthrough

## Goal

Show the value of the project with one deterministic command from a clean clone.

## Command

Install dependencies:

```bash
poetry install
```

Run the demo:

```bash
make run-demo
```

Equivalent direct CLI command:

```bash
poetry run incident-agent run-demo
```

## What it produces

The demo writes stable outputs under:

```text
artifacts/demo/portfolio-demo/
```

Important files:
- `artifacts/anomalies/anomalies.json`
- `artifacts/incidents/incidents.json`
- `artifacts/rca/rca_hypotheses.json`
- `artifacts/reports/final_reports.json`
- `artifacts/run_summary.json`
- `incident_report.md`
- `incident_report.html`
- `demo_manifest.json`

## Scenario

The demo uses the bundled deterministic sample incident:
- `data/sample/incident/anomaly_logs.csv`
- `data/sample/incident/anomaly_metrics.csv`

This scenario is stable and designed to surface:
- anomaly detection output
- a correlated incident candidate
- RCA hypothesis generation
- final report export

## How to inspect the result

1. Open `incident_report.md` for a concise summary.
2. Open `incident_report.html` for the presentable demo artifact.
3. Inspect `artifacts/incidents/incidents.json` to see the correlated incident candidate.
4. Inspect `artifacts/rca/rca_hypotheses.json` to review the heuristic RCA output.
5. Inspect `artifacts/run_summary.json` for run metadata and warnings.
