"""CLI entrypoints for the incident analysis agent."""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console

from incident_agent.services.analyze import analyze_from_files

app = typer.Typer(help="CLI for the AI incident analysis agent.")
console = Console()


@app.command()
def analyze(
    logs: Annotated[str, typer.Option(help="Path to a JSONL file with log events.")],
    metrics: Annotated[str, typer.Option(help="Path to a JSONL file with metric points.")],
) -> None:
    """Analyze logs and metrics and print structured reports."""

    reports = analyze_from_files(log_path=logs, metric_path=metrics)
    serialised = [report.model_dump(mode="json") for report in reports]
    console.print_json(json.dumps(serialised))


if __name__ == "__main__":
    app()
