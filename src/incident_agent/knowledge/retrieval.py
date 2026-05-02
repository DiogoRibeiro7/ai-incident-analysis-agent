"""Deterministic local retrieval over runbooks and historical incidents."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel

from incident_agent.core.settings import KnowledgeConfig
from incident_agent.schemas.rca import EvidenceBundle, IncidentSummaryFeatures, RootCauseHypothesis

_TEXT_EXTENSIONS = {".md", ".txt", ".log"}
_JSON_EXTENSIONS = {".json", ".jsonl"}
_MAX_FILE_BYTES = 1_000_000


class RetrievedSnippet(BaseModel):
    """One retrieved knowledge snippet injected into prompts/reports."""

    citation_id: str
    source_path: str
    score: float
    content: str


class _SnippetCandidate(BaseModel):
    citation_id: str
    source_path: str
    content: str


def retrieve_context(
    *,
    config: KnowledgeConfig,
    evidence_bundle: EvidenceBundle,
    summary_features: IncidentSummaryFeatures,
    root_cause_hypothesis: RootCauseHypothesis,
) -> list[RetrievedSnippet]:
    """Return deterministic top-k snippets for one incident context."""

    if not config.enabled or not config.source_paths:
        return []

    terms = _build_query_terms(evidence_bundle, summary_features, root_cause_hypothesis)
    if not terms:
        return []

    candidates = _load_candidates(config.source_paths)
    if not candidates:
        return []

    ranked: list[RetrievedSnippet] = []
    for candidate in candidates:
        score = _score_candidate(candidate.content, terms)
        if score <= 0:
            continue
        ranked.append(
            RetrievedSnippet(
                citation_id=candidate.citation_id,
                source_path=candidate.source_path,
                score=round(score, 6),
                content=_truncate(candidate.content, config.max_snippet_chars),
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.source_path, item.citation_id))
    return ranked[: max(config.top_k, 0)]


def _build_query_terms(
    evidence_bundle: EvidenceBundle,
    summary_features: IncidentSummaryFeatures,
    root_cause_hypothesis: RootCauseHypothesis,
) -> list[str]:
    terms: set[str] = set()
    terms.add(root_cause_hypothesis.suspected_root_cause_service.lower())
    terms.update(service.lower() for service in summary_features.impacted_services)
    terms.update(signal.lower() for signal in root_cause_hypothesis.contributing_signals)
    terms.update(signal.lower() for signal in evidence_bundle.contributing_signals)
    terms.update(item.anomaly_type.lower() for item in evidence_bundle.ranked_evidence)
    return sorted(term for term in terms if term.strip())


def _load_candidates(source_paths: list[str]) -> list[_SnippetCandidate]:
    candidates: list[_SnippetCandidate] = []
    for source_path in sorted(source_paths):
        base = Path(source_path)
        if base.is_file():
            candidates.extend(_load_file_candidates(base))
            continue
        if base.is_dir():
            for path in sorted(item for item in base.rglob("*") if item.is_file()):
                candidates.extend(_load_file_candidates(path))
    return candidates


def _load_file_candidates(path: Path) -> list[_SnippetCandidate]:
    if path.suffix.lower() not in _TEXT_EXTENSIONS | _JSON_EXTENSIONS:
        return []
    if path.stat().st_size > _MAX_FILE_BYTES:
        return []

    if path.suffix.lower() in _JSON_EXTENSIONS:
        chunks = _json_chunks(path)
    else:
        chunks = _text_chunks(path)

    candidates: list[_SnippetCandidate] = []
    for index, chunk in enumerate(chunks, start=1):
        normalized = " ".join(chunk.split())
        if not normalized:
            continue
        candidates.append(
            _SnippetCandidate(
                citation_id=f"{path.as_posix()}#chunk-{index}",
                source_path=path.as_posix(),
                content=normalized,
            )
        )
    return candidates


def _text_chunks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return chunks if chunks else [text.strip()]


def _json_chunks(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return rows

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [json.dumps(item, sort_keys=True) for item in payload]
    if isinstance(payload, dict):
        return [json.dumps(payload, sort_keys=True)]
    return [json.dumps(payload)]


def _score_candidate(text: str, terms: list[str]) -> float:
    lowered = text.lower()
    score = 0.0
    for term in terms:
        occurrences = lowered.count(term)
        if occurrences <= 0:
            continue
        score += float(occurrences)
        if "service" in term:
            score += 0.25 * occurrences
    return score


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
