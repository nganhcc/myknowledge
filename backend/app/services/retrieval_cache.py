import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import asdict
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.retrieval_types import RetrievedChunk


def normalize_query(query: str) -> str:
    """Return the canonical form used for retrieval cache identity."""
    normalized = unicodedata.normalize("NFKC", query)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def cache_key(
    workspace_id: uuid.UUID,
    workspace_version: int,
    query: str,
    top_k: int,
) -> str:
    payload = {
        "workspace_id": str(workspace_id),
        "workspace_version": workspace_version,
        "query": normalize_query(query),
        "top_k": top_k,
        "candidate_limit": settings.retrieval_candidate_limit,
        "rrf_k": settings.retrieval_rrf_k,
        "fts_config": settings.retrieval_fts_config,
        "reranker_enabled": settings.reranker_enabled,
        "reranker_model": settings.reranker_model,
        "embedding_model": settings.gemini_embedding_model,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (
        f"{settings.retrieval_cache_key_prefix}:v1:"
        f"{workspace_id}:{workspace_version}:{digest}"
    )


def serialize_chunks(chunks: list[RetrievedChunk]) -> str:
    serialized = [
        asdict(chunk)
        | {"chunk_id": str(chunk.chunk_id), "document_id": str(chunk.document_id)}
        for chunk in chunks
    ]
    return json.dumps(serialized)


def deserialize_chunks(value: str | bytes) -> list[RetrievedChunk]:
    data: list[dict[str, Any]] = json.loads(value)
    return [
        RetrievedChunk(
            chunk_id=uuid.UUID(item["chunk_id"]),
            document_id=uuid.UUID(item["document_id"]),
            document_title=item["document_title"],
            content=item["content"],
            page_number=item["page_number"],
            score=float(item["score"]),
        )
        for item in data
    ]


async def get_chunks(key: str) -> list[RetrievedChunk] | None:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        value = await client.get(key)
        if value is None:
            return None
        return deserialize_chunks(value)
    finally:
        await client.aclose()


async def set_chunks(key: str, chunks: list[RetrievedChunk]) -> None:
    client = aioredis.from_url(settings.redis_url)
    try:
        await client.set(
            key,
            serialize_chunks(chunks),
            ex=settings.retrieval_cache_ttl_seconds,
        )
    finally:
        await client.aclose()
