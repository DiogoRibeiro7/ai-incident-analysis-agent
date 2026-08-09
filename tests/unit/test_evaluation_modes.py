from __future__ import annotations

from incident_agent.schemas.eval import EvaluationMode, evaluation_modes


def test_default_evaluation_modes_are_canonical_and_ordered() -> None:
    modes = evaluation_modes(include_real_llm=False)

    assert modes == (
        EvaluationMode.HEURISTIC_ONLY,
        EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
        EvaluationMode.MOCK_LLM_RETRIEVAL,
    )
    assert len(set(modes)) == len(modes)


def test_real_evaluation_modes_are_opt_in() -> None:
    default_modes = evaluation_modes(include_real_llm=False)
    expanded_modes = evaluation_modes(include_real_llm=True)

    assert EvaluationMode.REAL_LLM_NO_RETRIEVAL not in default_modes
    assert EvaluationMode.REAL_LLM_RETRIEVAL not in default_modes
    assert expanded_modes == (
        EvaluationMode.HEURISTIC_ONLY,
        EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
        EvaluationMode.MOCK_LLM_RETRIEVAL,
        EvaluationMode.REAL_LLM_NO_RETRIEVAL,
        EvaluationMode.REAL_LLM_RETRIEVAL,
    )
    assert len(set(expanded_modes)) == len(expanded_modes)
