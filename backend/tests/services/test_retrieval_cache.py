import uuid

from app.services.retrieval_cache import (
    cache_key,
    deserialize_chunks,
    normalize_query,
    serialize_chunks,
)
from app.services.retrieval_types import RetrievedChunk


def test_normalize_query_collapses_unicode_whitespace_and_case() -> None:
    assert normalize_query("  Café\u00a0  POLICY\n") == "café policy"


def test_cache_key_includes_workspace_version_and_retrieval_settings() -> None:
    workspace_id = uuid.uuid4()
    first = cache_key(workspace_id, 1, "Question", 5)
    same_query = cache_key(workspace_id, 1, " question ", 5)
    changed_version = cache_key(workspace_id, 2, "Question", 5)
    changed_top_k = cache_key(workspace_id, 1, "Question", 3)

    assert first == same_query
    assert first != changed_version
    assert first != changed_top_k


def test_chunks_round_trip_through_json() -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Guide",
        content="Use the cache.",
        page_number=None,
        score=0.875,
    )

    assert deserialize_chunks(serialize_chunks([chunk])) == [chunk]