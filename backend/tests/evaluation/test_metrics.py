import uuid

import pytest
from app.evaluation.metrics import (
    EvaluationCase,
    SourceReference,
    aggregate_results,
    evaluate_case,
)
from app.services.retrieval import RetrievedChunk


def _chunk(title: str, page: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        content="content",
        page_number=page,
        score=0.0,
    )


def test_evaluate_case_calculates_ranked_metrics() -> None:
    case = EvaluationCase(
        case_id="case-1",
        question="Where?",
        expected_sources=(SourceReference("guide.pdf", 2),),
    )

    result = evaluate_case(
        case,
        [_chunk("other.pdf", 2), _chunk("guide.pdf", 2)],
        k_values=(1, 2),
    )

    assert result["hit_at_1"] == 0
    assert result["hit_at_2"] == 1
    assert result["recall_at_2"] == 1.0
    assert result["precision_at_2"] == 0.5
    assert result["mrr"] == 0.5


def test_evaluate_case_rejects_missing_expected_sources() -> None:
    case = EvaluationCase("case-1", "Where?", ())

    with pytest.raises(ValueError, match="expected_sources"):
        evaluate_case(case, [])


def test_aggregate_results_ignores_diagnostic_fields() -> None:
    results = [
        {"case_id": "one", "hit_at_1": 1, "returned_sources": []},
        {"case_id": "two", "hit_at_1": 0, "returned_sources": []},
    ]

    assert aggregate_results(results) == {"cases": 2, "hit_at_1": 0.5}