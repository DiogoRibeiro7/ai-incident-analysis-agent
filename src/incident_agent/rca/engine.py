"""RCA orchestration over correlated incidents."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.correlation.graph import ServiceDependencyGraph, load_service_dependency_graph
from incident_agent.rca.dependency import impacted_downstream_services
from incident_agent.rca.evidence import extract_contributing_signals, rank_evidence
from incident_agent.rca.scoring import score_root_candidates
from incident_agent.rca.summarize import summarize_incident_features
from incident_agent.schemas.incident import CorrelatedIncidentCandidate
from incident_agent.schemas.rca import EvidenceBundle, RCAResult, RootCauseHypothesis


class RCAConfig(BaseModel):
    """Configuration for RCA heuristics."""

    service_failure_bonus: float = 1.0
    downstream_bonus: float = 0.8
    ambiguity_delta: float = 0.75
    dependency_graph_path: str = "configs/service_dependencies.yaml"


def load_rca_config(path: str | Path = "configs/default.yaml") -> RCAConfig:
    """Load RCA config from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("rca", {})
    if not isinstance(section, dict):
        raise ValueError("The 'rca' section must be a mapping.")
    return RCAConfig.model_validate(section)


def perform_rca(
    incidents: list[CorrelatedIncidentCandidate],
    *,
    config: RCAConfig,
    dependency_graph: ServiceDependencyGraph,
) -> RCAResult:
    """Perform heuristic RCA and produce explicit intermediate artifacts."""

    bundles: list[EvidenceBundle] = []
    summaries = []
    hypotheses: list[RootCauseHypothesis] = []

    for incident in incidents:
        ranked = rank_evidence(incident.evidence)
        signals = extract_contributing_signals(ranked)

        primary_service, confidence, ambiguities = score_root_candidates(
            evidence=ranked,
            impacted_services=incident.impacted_services,
            dependency_graph=dependency_graph,
            service_failure_bonus=config.service_failure_bonus,
            downstream_bonus=config.downstream_bonus,
            ambiguity_delta=config.ambiguity_delta,
        )
        downstream = impacted_downstream_services(
            root_candidate=primary_service,
            impacted_services=incident.impacted_services,
            dependency_graph=dependency_graph,
        )

        bundle = EvidenceBundle(
            incident_id=incident.incident_id,
            ranked_evidence=ranked,
            contributing_signals=signals,
            impacted_downstream_services=downstream,
            unresolved_ambiguities=ambiguities,
        )
        summary = summarize_incident_features(incident, ranked)
        hypothesis = RootCauseHypothesis(
            incident_id=incident.incident_id,
            suspected_root_cause_service=primary_service,
            confidence_score=round(confidence, 4),
            contributing_signals=signals,
            impacted_downstream_services=downstream,
            unresolved_ambiguities=ambiguities,
            rationale=(
                f"Selected {primary_service} from severity-ranked evidence and dependency "
                "impact heuristics."
            ),
        )
        bundles.append(bundle)
        summaries.append(summary)
        hypotheses.append(hypothesis)

    return RCAResult(
        bundles=sorted(bundles, key=lambda item: item.incident_id),
        summaries=sorted(summaries, key=lambda item: item.incident_id),
        hypotheses=sorted(hypotheses, key=lambda item: item.incident_id),
    )


def load_dependency_graph_for_rca(config: RCAConfig) -> ServiceDependencyGraph:
    """Load dependency graph used by RCA heuristics."""

    return load_service_dependency_graph(config.dependency_graph_path)
