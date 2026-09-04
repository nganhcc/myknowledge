import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.workspace import Workspace
from app.services.reranker import rerank_chunks
from app.services.retrieval_cache import (
    cache_key,
    get_chunks,
    normalize_query,
    set_chunks,
)
from app.services.retrieval_types import RetrievedChunk

logger = structlog.get_logger()


@dataclass
class RetrievalCandidate:
    chunk: RetrievedChunk
    vector_rank: int | None = None
    lexical_rank: int | None = None
    fused_score: float = 0.0


def reciprocal_rank_fusion(
    vector_chunks: list[RetrievedChunk],
    lexical_chunks: list[RetrievedChunk],
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """Merge ranked results without comparing incompatible raw scores."""
    candidates: dict[uuid.UUID, RetrievalCandidate] = {}
    for rank, chunk in enumerate(vector_chunks, 1):
        candidate = candidates.setdefault(chunk.chunk_id, RetrievalCandidate(chunk))
        candidate.vector_rank = rank
        candidate.fused_score += 1.0 / (rrf_k + rank)
    for rank, chunk in enumerate(lexical_chunks, 1):
        candidate = candidates.setdefault(chunk.chunk_id, RetrievalCandidate(chunk))
        candidate.lexical_rank = rank
        candidate.fused_score += 1.0 / (rrf_k + rank)

    return [
        candidate.chunk
        for candidate in sorted(
            candidates.values(),
            key=lambda item: (-item.fused_score, str(item.chunk.chunk_id)),
        )
    ]


def _chunk_from_row(chunk: DocumentChunk, title: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_title=title,
        content=chunk.content,
        page_number=chunk.page_number,
        score=score,
    )


async def _vector_candidates(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk, Document.title, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance, DocumentChunk.id)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        _chunk_from_row(chunk, title, 1.0 - (distance or 1.0))
        for chunk, title, distance in result.all()
    ]


async def _lexical_candidates(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[RetrievedChunk]:
    query_text = query.strip()
    if not query_text:
        return []
    ts_query = func.websearch_to_tsquery(settings.retrieval_fts_config, query_text)
    rank = func.ts_rank_cd(DocumentChunk.content_search, ts_query)
    stmt = (
        select(DocumentChunk, Document.title, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.content_search.op("@@")(ts_query),
        )
        .order_by(rank.desc(), DocumentChunk.id)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_chunk_from_row(chunk, title, score) for chunk, title, score in result.all()]


async def retrieve_chunks(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
    query: str = "",
) -> list[RetrievedChunk]:
    """Return hybrid vector/FTS results, ordered by reciprocal rank fusion."""
    normalized_query = normalize_query(query)
    workspace_version = await db.scalar(
        select(Workspace.retrieval_version).where(Workspace.id == workspace_id)
    )
    if workspace_version is None:
        raise ValueError(f"Workspace {workspace_id} not found")
    key = cache_key(workspace_id, workspace_version, normalized_query, top_k)
    if settings.retrieval_cache_enabled:
        try:
            cached = await get_chunks(key)
        except Exception as error:  # noqa: BLE001
            logger.warning("retrieval_cache_error", operation="get", error=str(error))
        else:
            if cached is not None:
                logger.info("retrieval_cache_hit", workspace_id=str(workspace_id))
                return cached
            logger.info("retrieval_cache_miss", workspace_id=str(workspace_id))

    candidate_limit = max(top_k, settings.retrieval_candidate_limit)
    vector_chunks = await _vector_candidates(
        db, workspace_id, query_embedding, candidate_limit
    )
    lexical_chunks = await _lexical_candidates(
        db, workspace_id, normalized_query, candidate_limit
    )
    fused_chunks = reciprocal_rank_fusion(
        vector_chunks,
        lexical_chunks,
        settings.retrieval_rrf_k,
    )[:candidate_limit]
    chunks = await rerank_chunks(normalized_query, fused_chunks, top_k)
    if settings.retrieval_cache_enabled:
        try:
            await set_chunks(key, chunks)
        except Exception as error:  # noqa: BLE001
            logger.warning("retrieval_cache_error", operation="set", error=str(error))
    return chunks
