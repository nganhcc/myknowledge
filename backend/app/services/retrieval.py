import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    page_number: int | None
    score: float


async def retrieve_chunks(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve top_k document chunks similar to query_embedding within the workspace."""
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk, Document.title, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.workspace_id == workspace_id)
        .order_by(distance)
        .limit(top_k)
    )
    result = await db.execute(stmt)

    retrieved = []
    for chunk, title, dist in result.all():
        score = 1.0 - (dist if dist is not None else 1.0)
        retrieved.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=title,
                content=chunk.content,
                page_number=chunk.page_number,
                score=score,
            )
        )
    return retrieved
