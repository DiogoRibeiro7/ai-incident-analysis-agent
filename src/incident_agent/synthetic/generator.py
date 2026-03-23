"""Synthetic incident scenario generation for demos and evaluation."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from incident_agent.schemas.eval import BenchmarkScenario, SyntheticScenarioGeneratorConfig


def generate_benchmark_scenarios(
    configs: Iterable[tuple[str, str, SyntheticScenarioGeneratorConfig]],
    *,
    output_root: str | Path,
) -> list[BenchmarkScenario]:
    """Generate multiple benchmark scenarios under one root directory."""

    root = Path(output_root)
    scenarios: list[BenchmarkScenario] = []
    for scenario_id, description, config in configs:
        scenarios.append(
            generate_benchmark_scenario(
                scenario_id=scenario_id,
                description=description,
                config=config,
                output_root=root,
            )
        )
    return scenarios


def generate_benchmark_scenario(
    *,
    scenario_id: str,
    description: str,
    config: SyntheticScenarioGeneratorConfig,
    output_root: str | Path,
) -> BenchmarkScenario:
    """Generate one synthetic benchmark scenario with logs, metrics, and metadata."""

    scenario_dir = Path(output_root) / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    timestamps = _timeline(config.start_time, config.duration_minutes, config.interval_minutes)
    services = _services_for(config)
    randomizer = random.Random(config.seed)
    impacted = config.impacted_services or [config.root_cause_service]

    logs = _generate_logs(
        scenario_id=scenario_id,
        config=config,
        timestamps=timestamps,
        services=services,
        randomizer=randomizer,
    )
    metrics = _generate_metrics(
        config=config,
        timestamps=timestamps,
        services=services,
        impacted_services=impacted,
        randomizer=randomizer,
    )
    metadata = {
        "scenario_id": scenario_id,
        "scenario_type": config.scenario_type,
        "root_cause_service": config.root_cause_service,
        "impacted_services": impacted,
        "start_time": _to_utc(config.start_time).isoformat(),
        "duration_minutes": config.duration_minutes,
        "interval_minutes": config.interval_minutes,
        "seed": config.seed,
    }

    logs_path = scenario_dir / "logs.csv"
    metrics_path = scenario_dir / "metrics.csv"
    metadata_path = scenario_dir / "metadata.json"
    _write_csv(logs_path, ["timestamp", "service", "severity", "message", "trace_id"], logs)
    _write_csv(
        metrics_path,
        ["timestamp", "service", "metric_name", "value", "unit"],
        metrics,
    )
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return BenchmarkScenario(
        scenario_id=scenario_id,
        description=description,
        logs_path=str(logs_path),
        metrics_path=str(metrics_path),
        metadata_path=str(metadata_path),
        expected_root_cause=config.root_cause_service,
        expected_impacted_services=impacted,
        expected_min_incidents=1,
        generator=config,
    )


def _generate_logs(
    *,
    scenario_id: str,
    config: SyntheticScenarioGeneratorConfig,
    timestamps: list[datetime],
    services: list[str],
    randomizer: random.Random,
) -> list[list[str]]:
    rows: list[list[str]] = []
    for index, timestamp in enumerate(timestamps):
        incident_active = index >= max(1, len(timestamps) // 2)
        for service in services:
            severity = "INFO"
            message = "Healthy request flow"
            if incident_active and service == config.root_cause_service:
                severity, message = _root_log_message(config.scenario_type, randomizer)
            elif incident_active and service in (config.impacted_services or []):
                severity = "WARN"
                message = "Downstream symptoms detected"
            rows.append(
                [
                    _format_ts(timestamp),
                    service,
                    severity,
                    message,
                    f"{scenario_id}-{service}-{index:03d}",
                ]
            )
    return rows


def _generate_metrics(
    *,
    config: SyntheticScenarioGeneratorConfig,
    timestamps: list[datetime],
    services: list[str],
    impacted_services: list[str],
    randomizer: random.Random,
) -> list[list[str]]:
    rows: list[list[str]] = []
    for index, timestamp in enumerate(timestamps):
        incident_factor = 1.0 if index < max(1, len(timestamps) // 2) else 2.8
        for service in services:
            impacted = service == config.root_cause_service or service in impacted_services
            rows.extend(
                _service_metrics(
                    timestamp=timestamp,
                    service=service,
                    scenario_type=config.scenario_type,
                    incident_factor=incident_factor,
                    impacted=impacted,
                    randomizer=randomizer,
                )
            )
    return rows


def _service_metrics(
    *,
    timestamp: datetime,
    service: str,
    scenario_type: str,
    incident_factor: float,
    impacted: bool,
    randomizer: random.Random,
) -> list[list[str]]:
    latency = float(120 + randomizer.randint(-10, 15))
    error_rate = 0.01 + randomizer.random() * 0.01
    cpu = float(35 + randomizer.randint(-3, 4))
    memory = float(420 + randomizer.randint(-20, 25))
    requests = 1200 + randomizer.randint(-80, 80)
    availability = 0.0

    if impacted:
        if scenario_type == "latency_degradation":
            latency *= incident_factor * 2.4
        elif scenario_type == "error_burst":
            error_rate *= incident_factor * 8
        elif scenario_type == "dependency_cascade":
            latency *= incident_factor * 2.0
            error_rate *= incident_factor * 6
        elif scenario_type == "traffic_drop":
            requests = int(requests / max(incident_factor * 1.9, 1.0))
        elif scenario_type == "resource_exhaustion":
            cpu *= incident_factor * 1.8
            memory *= incident_factor * 1.6
            latency *= incident_factor * 1.8
        elif scenario_type == "partial_outage":
            availability = min(1.0, 0.2 * incident_factor)
            error_rate *= incident_factor * 10
            latency *= incident_factor * 2.5

    return [
        [_format_ts(timestamp), service, "error_rate", f"{error_rate:.4f}", "ratio"],
        [_format_ts(timestamp), service, "request_latency_ms", f"{latency:.2f}", "ms"],
        [_format_ts(timestamp), service, "cpu_usage", f"{cpu:.2f}", "percent"],
        [_format_ts(timestamp), service, "memory_usage_mb", f"{memory:.2f}", "mb"],
        [_format_ts(timestamp), service, "request_count", str(requests), "count"],
        [_format_ts(timestamp), service, "service_unavailable", f"{availability:.2f}", "ratio"],
    ]


def _root_log_message(scenario_type: str, randomizer: random.Random) -> tuple[str, str]:
    messages = {
        "latency_degradation": ("WARN", "Request latency exceeded SLO during peak traffic"),
        "error_burst": ("ERROR", "Unhandled exception burst observed in request handler"),
        "dependency_cascade": ("ERROR", "Upstream dependency timeout is cascading downstream"),
        "traffic_drop": ("WARN", "Traffic volume dropped sharply from expected baseline"),
        "resource_exhaustion": (
            "CRITICAL",
            "CPU and memory saturation causing service instability",
        ),
        "partial_outage": ("CRITICAL", "Partial outage detected across multiple service instances"),
    }
    severity, message = messages[scenario_type]
    if randomizer.random() > 0.7:
        return severity, f"{message}; automated mitigation pending"
    return severity, message


def _services_for(config: SyntheticScenarioGeneratorConfig) -> list[str]:
    services = {config.root_cause_service, *config.supporting_services, *config.impacted_services}
    return sorted(services)


def _timeline(start_time: datetime, duration_minutes: int, interval_minutes: int) -> list[datetime]:
    start = _to_utc(start_time)
    points = max(2, (duration_minutes // interval_minutes) + 1)
    return [start + timedelta(minutes=index * interval_minutes) for index in range(points)]


def _to_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _format_ts(timestamp: datetime) -> str:
    return _to_utc(timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    lines = [",".join(header)]
    lines.extend(",".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
