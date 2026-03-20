"""Service dependency graph loading and traversal helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from incident_agent.core.settings import load_settings_from_yaml


class ServiceRelations(BaseModel):
    """Dependency relationships for one service."""

    upstream: list[str] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)


class ServiceDependencyGraph(BaseModel):
    """Service dependency graph."""

    services: dict[str, ServiceRelations] = Field(default_factory=dict)

    def are_related(self, source: str, target: str) -> bool:
        """Return True if services are directly related in any direction."""

        if source == target:
            return True
        source_relations = self.services.get(source, ServiceRelations())
        target_relations = self.services.get(target, ServiceRelations())
        return (
            target in source_relations.upstream
            or target in source_relations.downstream
            or source in target_relations.upstream
            or source in target_relations.downstream
        )

    def downstream_impacted_count(self, service: str, impacted_services: set[str]) -> int:
        """Count impacted downstream services for a candidate root."""

        relations = self.services.get(service, ServiceRelations())
        return sum(1 for downstream in relations.downstream if downstream in impacted_services)

    def upstream_impacted_count(self, service: str, impacted_services: set[str]) -> int:
        """Count impacted upstream services for a candidate root."""

        relations = self.services.get(service, ServiceRelations())
        return sum(1 for upstream in relations.upstream if upstream in impacted_services)


def load_service_dependency_graph(path: str | Path) -> ServiceDependencyGraph:
    """Load service dependency graph from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    if "services" not in loaded:
        raise ValueError("Dependency graph YAML must include a top-level 'services' mapping.")
    return ServiceDependencyGraph.model_validate(loaded)
