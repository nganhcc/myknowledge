import re
from dataclasses import dataclass
from typing import Any

from app.services.retrieval import RetrievedChunk


@dataclass(frozen=True)
class SourceReference:
    """A portable benchmark reference to a document location."""

    document: str
    page: int | None = None


@dataclass(frozen=True)
class EvaluationCase:
    """One question and its acceptable supporting source locations."""

    case_id: str
    question: str
    expected_sources: tuple[SourceReference, ...]
    ground_truth: str | None = None
    answerable: bool = True


def source_matches(chunk: RetrievedChunk, reference: SourceReference) -> bool:
    """Match by title or filename-like title, and optionally by page."""
    if chunk.document_title != reference.document:
        return False
    return reference.page is None or chunk.page_number == reference.page


def _relevant_positions(
    chunks: list[RetrievedChunk], expected_sources: tuple[SourceReference, ...]
) -> set[int]:
    return {
        position
        for position, chunk in enumerate(chunks, 1)
        if any(source_matches(chunk, reference) for reference in expected_sources)
    }


def citation_metrics(
    answer: str,
    retrieved_chunks: list[RetrievedChunk],
    expected_sources: tuple[SourceReference, ...],
) -> dict[str, Any]:
    """Score source labels in an answer against retrieved and expected sources."""
    labels = [
        int(value)
        for value in re.findall(r"\[Source\s+(\d+)\]", answer, re.IGNORECASE)
    ]
    valid_positions = [label for label in labels if 1 <= label <= len(retrieved_chunks)]
    unique_positions = set(valid_positions)
    expected_positions = {
        position
        for position in unique_positions
        if any(
            source_matches(retrieved_chunks[position - 1], reference)
            for reference in expected_sources
        )
    }
    return {
        "citation_count": len(labels),
        "valid_citation_count": len(valid_positions),
        "invalid_citation_count": len(labels) - len(valid_positions),
        "citation_validity": len(valid_positions) / len(labels) if labels else 0.0,
        "citation_precision": (
            len(expected_positions) / len(unique_positions) if unique_positions else 0.0
        ),
        "citation_recall": (
            len(expected_positions) / len(expected_sources) if expected_sources else 0.0
        ),
        "uncited_answer": int(not labels),
    }


def evaluate_case(
    case: EvaluationCase,
    retrieved_chunks: list[RetrievedChunk],
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, Any]:
    """Calculate deterministic retrieval metrics for one benchmark case."""
    if not case.expected_sources:
        raise ValueError(f"Case {case.case_id} must define expected_sources")
    if any(k < 1 for k in k_values):
        raise ValueError("k_values must contain only positive integers")

    relevant_positions = _relevant_positions(retrieved_chunks, case.expected_sources)
    result: dict[str, Any] = {"case_id": case.case_id}
    for k in k_values:
        top_k = {position for position in relevant_positions if position <= k}
        result[f"hit_at_{k}"] = int(bool(top_k))
        result[f"recall_at_{k}"] = len(top_k) / len(case.expected_sources)
        result[f"precision_at_{k}"] = len(top_k) / min(k, len(retrieved_chunks)) if retrieved_chunks else 0.0

    result["mrr"] = (
        1.0 / min(relevant_positions) if relevant_positions else 0.0
    )
    return result


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, float | int]:
    """Return arithmetic means for numeric per-case metrics."""
    if not results:
        return {"cases": 0}
    metric_names = [
        key
        for key, value in results[0].items()
        if key != "case_id" and isinstance(value, (int, float))
    ]
    aggregate: dict[str, float | int] = {"cases": len(results)}
    for name in metric_names:
        values = [float(result[name]) for result in results]
        aggregate[name] = sum(values) / len(values)
    return aggregate