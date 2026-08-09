"""Synthetic incident scenario generation for demos and evaluation."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from incident_agent.schemas.eval import BenchmarkScenario, SyntheticScenarioGeneratorConfig

_HEALTHY_TYPES = {"healthy_stable", "healthy_noisy", "normal_traffic_variability"}
_LATENCY_TYPES = {"transient_latency_spike", "latency_degradation", "gradual_latency_drift"}
_ERROR_TYPES = {"error_burst", "persistent_error_rate"}
_METRICS_ONLY_TYPES = {"metrics_only_degradation", "missing_logs"}
_CPU_TYPES = {"cpu_saturation"}
_MEMORY_TYPES = {"memory_saturation"}
_RESOURCE_TYPES = {"resource_exhaustion", "resource_anomaly_no_impact"}
_TRAFFIC_TYPES = {"traffic_drop", "traffic_disappearance", "isolated_low_volume_bucket"}
_AVAILABILITY_TYPES = {
    "partial_outage",
    "heartbeat_loss",
    "temporary_unavailability",
}
_DISTRIBUTED_TYPES = {
    "dependency_cascade",
    "upstream_root_cause",
    "downstream_symptoms",
    "unrelated_simultaneous",
    "sparse_observations",
}
_AMBIGUITY_TYPES = {"ambiguous_root_causes", "contradictory_telemetry"}


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
        incident_expected=config.scenario_type not in _HEALTHY_TYPES,
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
    if config.scenario_type == "missing_logs":
        return []

    rows: list[list[str]] = []
    total_points = len(timestamps)
    for index, timestamp in enumerate(timestamps):
        incident_active = _incident_active(
            scenario_type=config.scenario_type,
            index=index,
            total_points=total_points,
        )
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
    if config.scenario_type == "missing_metrics":
        return []

    rows: list[list[str]] = []
    total_points = len(timestamps)
    for index, timestamp in enumerate(timestamps):
        incident_factor = _incident_factor(
            scenario_type=config.scenario_type,
            index=index,
            total_points=total_points,
        )
        for service in services:
            impacted = config.scenario_type not in _HEALTHY_TYPES and (
                service == config.root_cause_service or service in impacted_services
            )
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
    noise = 2 if scenario_type == "healthy_stable" else 15
    latency = float(120 + randomizer.randint(-noise, noise))
    error_rate = 0.01 + randomizer.random() * (0.006 if scenario_type == "healthy_stable" else 0.02)
    cpu = float(35 + randomizer.randint(-3, 4))
    memory = float(420 + randomizer.randint(-20, 25))
    requests = 1200 + randomizer.randint(-80, 80)
    availability = 0.0

    if scenario_type == "normal_traffic_variability":
        requests += randomizer.randint(-180, 180)

    if impacted:
        if scenario_type in _LATENCY_TYPES or scenario_type in _METRICS_ONLY_TYPES:
            latency *= incident_factor * 2.4
        elif scenario_type in _ERROR_TYPES:
            error_rate *= incident_factor * 8
        elif scenario_type in _DISTRIBUTED_TYPES or scenario_type in _AMBIGUITY_TYPES:
            latency *= incident_factor * 2.0
            error_rate *= incident_factor * 6
        elif scenario_type in _TRAFFIC_TYPES:
            requests = int(requests / max(incident_factor * 1.9, 1.0))
            if scenario_type == "traffic_disappearance":
                requests = 0
        elif scenario_type == "resource_exhaustion":
            cpu *= incident_factor * 1.8
            memory *= incident_factor * 1.6
            latency *= incident_factor * 1.8
        elif scenario_type in _CPU_TYPES:
            cpu *= incident_factor * 2.3
            latency *= incident_factor * 1.4
        elif scenario_type in _MEMORY_TYPES or scenario_type == "resource_anomaly_no_impact":
            memory *= incident_factor * 2.1
        elif scenario_type in _AVAILABILITY_TYPES:
            availability = min(1.0, 0.2 * incident_factor)
            if scenario_type in {"heartbeat_loss", "temporary_unavailability"}:
                availability = min(1.0, 0.4 * incident_factor)
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
        "healthy_stable": ("INFO", "Healthy request flow"),
        "healthy_noisy": ("INFO", "Benign noisy telemetry within expected range"),
        "normal_traffic_variability": ("INFO", "Traffic varied within expected daily range"),
        "transient_latency_spike": ("WARN", "Brief request latency spike exceeded SLO"),
        "latency_degradation": ("WARN", "Request latency exceeded SLO during peak traffic"),
        "gradual_latency_drift": ("WARN", "Request latency drifted upward across the window"),
        "error_burst": ("ERROR", "Unhandled exception burst observed in request handler"),
        "persistent_error_rate": ("ERROR", "Error rate remained elevated across the window"),
        "error_logs_only": ("ERROR", "Application error logs emitted without metric degradation"),
        "metrics_only_degradation": ("INFO", "Metric-only degradation without error logs"),
        "cpu_saturation": ("CRITICAL", "CPU saturation causing service instability"),
        "memory_saturation": ("CRITICAL", "Memory saturation causing service instability"),
        "resource_anomaly_no_impact": ("WARN", "Resource anomaly observed without user impact"),
        "dependency_cascade": ("ERROR", "Upstream dependency timeout is cascading downstream"),
        "upstream_root_cause": ("ERROR", "Upstream dependency failure is driving symptoms"),
        "downstream_symptoms": ("WARN", "Downstream symptoms detected from upstream issue"),
        "unrelated_simultaneous": (
            "ERROR",
            "Independent service anomalies occurred simultaneously",
        ),
        "traffic_drop": ("WARN", "Traffic volume dropped sharply from expected baseline"),
        "traffic_disappearance": ("CRITICAL", "Traffic disappeared for the service"),
        "isolated_low_volume_bucket": ("WARN", "Single low-volume bucket observed"),
        "resource_exhaustion": (
            "CRITICAL",
            "CPU and memory saturation causing service instability",
        ),
        "partial_outage": ("CRITICAL", "Partial outage detected across multiple service instances"),
        "heartbeat_loss": ("CRITICAL", "Service heartbeat was lost"),
        "temporary_unavailability": ("CRITICAL", "Service was temporarily unavailable"),
        "missing_observability": ("WARN", "Observability signal is missing during investigation"),
        "ambiguous_root_causes": ("WARN", "Multiple services show plausible causal evidence"),
        "contradictory_telemetry": ("WARN", "Telemetry is contradictory across signals"),
        "insufficient_evidence": ("WARN", "Evidence is insufficient for a confident root cause"),
        "missing_logs": ("WARN", "Logs are missing for the incident window"),
        "missing_metrics": ("ERROR", "Error logs indicate degradation while metrics are missing"),
        "sparse_observations": ("WARN", "Sparse observations show intermittent degradation"),
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


def _incident_active(*, scenario_type: str, index: int, total_points: int) -> bool:
    if scenario_type in _HEALTHY_TYPES:
        return False
    midpoint = max(1, total_points // 2)
    if scenario_type in {"transient_latency_spike", "isolated_low_volume_bucket"}:
        return index == midpoint
    if scenario_type == "temporary_unavailability":
        return midpoint <= index <= min(total_points - 1, midpoint + 1)
    return index >= midpoint


def _incident_factor(*, scenario_type: str, index: int, total_points: int) -> float:
    if not _incident_active(scenario_type=scenario_type, index=index, total_points=total_points):
        return 1.0
    if scenario_type == "gradual_latency_drift":
        midpoint = max(1, total_points // 2)
        return 1.4 + ((index - midpoint + 1) * 0.35)
    if scenario_type in {"transient_latency_spike", "isolated_low_volume_bucket"}:
        return 3.8
    return 2.8


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
