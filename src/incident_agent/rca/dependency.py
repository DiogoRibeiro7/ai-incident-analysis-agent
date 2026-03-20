"""Dependency reasoning utilities for RCA."""

from __future__ import annotations

from incident_agent.correlation.graph import ServiceDependencyGraph


def impacted_downstream_services(
    *,
    root_candidate: str,
    impacted_services: list[str],
    dependency_graph: ServiceDependencyGraph,
) -> list[str]:
    """Return impacted services that are downstream from the candidate root service."""

    if root_candidate == "global":
        return []

    impacted = set(impacted_services)
    downstream = dependency_graph.services.get(root_candidate)
    if downstream is None:
        return []

    matches = [service for service in downstream.downstream if service in impacted]
    return sorted(matches)
