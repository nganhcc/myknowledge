from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.retrieval import RetrievedChunk

logger = structlog.get_logger()


class Reranker(Protocol):
    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]: ...


class LocalCrossEncoderReranker:
    """Lazily load bge-reranker-base and keep blocking inference off the event loop."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: object | None = None

    def _load_model(self) -> object:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not chunks or not query.strip():
            return list(chunks)[:top_k]

        pairs = [(query, chunk.content) for chunk in chunks]

        def predict() -> list[float]:
            model = self._load_model()
            scores = model.predict(pairs)  # type: ignore[attr-defined]
            return [float(score) for score in scores]

        scores = await asyncio.to_thread(predict)
        ranked = sorted(
            zip(scores, chunks, strict=True),
            key=lambda item: (-item[0], str(item[1].chunk_id)),
        )
        return [chunk for _, chunk in ranked[:top_k]]


_reranker: LocalCrossEncoderReranker | None = None


def get_reranker() -> Reranker | None:
    global _reranker
    if not settings.reranker_enabled:
        return None
    if _reranker is None:
        _reranker = LocalCrossEncoderReranker(settings.reranker_model)
    return _reranker


async def rerank_chunks(
    query: str,
    chunks: Sequence[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    """Rerank candidates, returning the original order when unavailable or failing."""
    fallback = list(chunks)[:top_k]
    reranker = get_reranker()
    if reranker is None:
        return fallback
    try:
        ranked = await reranker.rerank(query, chunks, top_k)
        valid_ids = {chunk.chunk_id for chunk in chunks}
        seen_ids = set()
        validated = []
        for chunk in ranked:
            if chunk.chunk_id in valid_ids and chunk.chunk_id not in seen_ids:
                validated.append(chunk)
                seen_ids.add(chunk.chunk_id)
        for chunk in fallback:
            if chunk.chunk_id not in seen_ids:
                validated.append(chunk)
                seen_ids.add(chunk.chunk_id)
        return validated[:top_k]
    except Exception as error:  # noqa: BLE001
        logger.warning("reranker_unavailable_using_rrf", error=str(error))
        return fallback