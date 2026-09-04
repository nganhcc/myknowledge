import uuid

from app.services.retrieval import RetrievedChunk, reciprocal_rank_fusion


def _chunk() -> RetrievedChunk:
    chunk_id = uuid.uuid4()
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        document_title="Document",
        content="Content",
        page_number=1,
        score=0.0,
    )


def test_reciprocal_rank_fusion_promotes_results_found_by_both_searches() -> None:
    shared = _chunk()
    vector_only = _chunk()
    lexical_only = _chunk()

    results = reciprocal_rank_fusion(
        [shared, vector_only], [lexical_only, shared], rrf_k=60
    )

    assert results[0] is shared
    assert {chunk.chunk_id for chunk in results} == {
        shared.chunk_id,
        vector_only.chunk_id,
        lexical_only.chunk_id,
    }


def test_reciprocal_rank_fusion_is_deterministic_for_equal_scores() -> None:
    first = _chunk()
    second = _chunk()
    expected = sorted([first, second], key=lambda chunk: str(chunk.chunk_id))

    results = reciprocal_rank_fusion([first], [second], rrf_k=60)

    assert results == expected