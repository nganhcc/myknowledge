import json
import time
import uuid
from collections.abc import AsyncGenerator

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.models.usage_log import UsageLog
from app.models.user import User
from app.services.embedder import embed_texts
from app.services.retrieval import RetrievedChunk, retrieve_chunks
from app.services.workspace import get_workspace

logger = structlog.get_logger()


class ConversationNotFoundError(Exception):
    """Conversation not found or access denied."""


class ChatServiceError(Exception):
    """Base exception for Chat Service errors."""


SYSTEM_PROMPT = (
    "You are an assistant designed to answer questions based ONLY on the provided context.\n"
    "For any statement you make that is supported by a source in the context, cite it by placing "
    "[Source X] at the end of the sentence or statement (e.g. [Source 1], [Source 2]).\n"
    "If the context doesn't contain the answer, say 'I cannot find the answer in the provided documents.'\n"
    "Do not make up facts or use outside knowledge."
)


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Format chunks as plain text context with Source tags."""
    if not chunks:
        return "No relevant context found in workspace."

    context_parts = []
    for idx, c in enumerate(chunks, 1):
        page_str = f"Page {c.page_number}" if c.page_number else "Unknown Page"
        context_parts.append(
            f"[Source {idx}] Title: {c.document_title} — {page_str}\n"
            f"Content: {c.content}\n"
        )
    return "\n".join(context_parts)


async def get_or_create_conversation(
    db: AsyncSession,
    actor: User,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    first_message_text: str,
) -> Conversation:
    """Get conversation if conversation_id provided, or create a new one."""
    await get_workspace(db, actor, workspace_id)

    if conversation_id:
        conversation = await db.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.workspace_id != workspace_id
            or conversation.user_id != actor.id
        ):
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    # Create new conversation
    title = first_message_text[:60]
    if len(first_message_text) > 60:
        title += "..."

    conversation = Conversation(
        workspace_id=workspace_id,
        user_id=actor.id,
        title=title,
    )
    db.add(conversation)
    await db.flush()  # Get conversation ID
    return conversation


async def save_chat_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_message_text: str,
    assistant_message_text: str,
    citations: list[dict],
) -> tuple[Message, Message]:
    """Save user and assistant messages to DB."""
    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=user_message_text,
    )
    assistant_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_message_text,
        citations=citations,
    )
    db.add_all([user_msg, assistant_msg])
    await db.commit()
    await db.refresh(assistant_msg)
    return user_msg, assistant_msg


async def write_usage_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """Log LLM usage and estimate cost (fire-and-forget style)."""
    try:
        # Cost estimate based on Gemini Flash pricing: $0.075 / 1M input, $0.30 / 1M output
        estimated_cost = (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000
        log = UsageLog(
            user_id=user_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        logger.error("failed_to_write_usage_log", error=str(e))


async def chat_non_streaming(
    db: AsyncSession,
    actor: User,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    question: str,
) -> tuple[Conversation, Message, list[dict]]:
    """Execute standard non-streaming RAG chat, useful for tests/internal calls."""
    start_time = time.perf_counter()
    api_key = settings.gemini_api_key
    if not api_key:
        raise ChatServiceError("GEMINI_API_KEY is not configured")

    conversation = await get_or_create_conversation(
        db, actor, workspace_id, conversation_id, question
    )

    # 1. Embed question
    embeddings = await embed_texts([question])
    if not embeddings:
        raise ChatServiceError("Failed to embed question")
    query_embedding = embeddings[0]

    # 2. Retrieve context chunks
    chunks = await retrieve_chunks(db, workspace_id, query_embedding, top_k=5)
    context_text = build_context(chunks)

    # 3. Formulate history turns
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    history_messages = (await db.execute(stmt)).scalars().all()

    contents = []
    for msg in history_messages:
        role = "user" if msg.role == MessageRole.USER else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})

    # Append current turn with context
    contents.append(
        {
            "role": "user",
            "parts": [{"text": f"Context:\n{context_text}\n\nQuestion: {question}"}],
        }
    )

    # 4. Generate answer via Gemini REST API
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_generation_model}:generateContent?key={api_key}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=45.0)
        if response.status_code != 200:
            logger.error(
                "gemini_generation_api_failed",
                status_code=response.status_code,
                body=response.text,
            )
            raise ChatServiceError(
                f"Gemini API returned status {response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            answer = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            logger.error("unexpected_gemini_response_structure", response=data)
            raise ChatServiceError("Unexpected response structure from Gemini API")

        # Parse usage details
        usage_metadata = data.get("usageMetadata", {})
        input_tokens = usage_metadata.get("promptTokenCount", 0)
        output_tokens = usage_metadata.get("candidatesTokenCount", 0)

    # 5. Build citations
    citations = []
    for idx, c in enumerate(chunks, 1):
        citations.append(
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "document_name": c.document_title,
                "page": c.page_number,
            }
        )

    # 6. Save messages & log usage
    _, assistant_msg = await save_chat_messages(
        db, conversation.id, question, answer, citations
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    await write_usage_log(
        db,
        actor.id,
        workspace_id,
        conversation.id,
        settings.gemini_generation_model,
        input_tokens,
        output_tokens,
        latency_ms,
    )

    return conversation, assistant_msg, citations


async def chat_streaming(
    db: AsyncSession,
    actor: User,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    question: str,
) -> AsyncGenerator[str]:
    """Execute streaming RAG chat. Yields SSE events formatted as strings."""
    start_time = time.perf_counter()
    api_key = settings.gemini_api_key
    if not api_key:
        yield f"event: error\ndata: {json.dumps({'detail': 'GEMINI_API_KEY is not configured'})}\n\n"
        return

    try:
        conversation = await get_or_create_conversation(
            db, actor, workspace_id, conversation_id, question
        )
    except ConversationNotFoundError as e:
        yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
        return
    except Exception:
        yield f"event: error\ndata: {json.dumps({'detail': 'Workspace access denied'})}\n\n"
        return

    # Yield first event: conversation details
    yield f"event: conversation\ndata: {json.dumps({'conversation_id': str(conversation.id), 'title': conversation.title})}\n\n"

    # 1. Embed question
    try:
        embeddings = await embed_texts([question])
        if not embeddings:
            raise ChatServiceError("Failed to embed question")
        query_embedding = embeddings[0]
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': f'Embedding error: {e}'})}\n\n"
        return

    # 2. Retrieve context chunks
    try:
        chunks = await retrieve_chunks(db, workspace_id, query_embedding, top_k=5)
        context_text = build_context(chunks)
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': f'Retrieval error: {e}'})}\n\n"
        return

    # Yield citation list immediately
    citations = []
    for idx, c in enumerate(chunks, 1):
        citations.append(
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "document_name": c.document_title,
                "page": c.page_number,
            }
        )
    yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"

    # 3. Formulate history turns
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    history_messages = (await db.execute(stmt)).scalars().all()

    contents = []
    for msg in history_messages:
        role = "user" if msg.role == MessageRole.USER else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})

    contents.append(
        {
            "role": "user",
            "parts": [{"text": f"Context:\n{context_text}\n\nQuestion: {question}"}],
        }
    )

    # 4. Stream response from Gemini streamGenerateContent API
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_generation_model}:streamGenerateContent?key={api_key}&alt=sse"
    )

    answer_parts = []
    input_tokens = 0
    output_tokens = 0

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url, json=payload, timeout=45.0
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error(
                        "gemini_stream_api_failed",
                        status_code=response.status_code,
                        body=body.decode(),
                    )
                    yield f"event: error\ndata: {json.dumps({'detail': f'Gemini Stream API failed: {response.status_code}'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        chunk_data = json.loads(data_str)

                        # Extract text
                        try:
                            text_chunk = chunk_data["candidates"][0]["content"][
                                "parts"
                            ][0]["text"]
                            answer_parts.append(text_chunk)
                            yield f"event: token\ndata: {json.dumps({'token': text_chunk})}\n\n"
                        except (KeyError, IndexError):
                            # usageMetadata usually comes in the last chunk
                            pass

                        # Extract usageMetadata if available
                        if "usageMetadata" in chunk_data:
                            meta = chunk_data["usageMetadata"]
                            input_tokens = meta.get("promptTokenCount", input_tokens)
                            output_tokens = meta.get(
                                "candidatesTokenCount", output_tokens
                            )

    except Exception as e:
        logger.exception("streaming_exception")
        yield f"event: error\ndata: {json.dumps({'detail': f'Stream read error: {e}'})}\n\n"
        return

    answer = "".join(answer_parts)

    # 5. Save generated text and citations to database
    try:
        _, assistant_msg = await save_chat_messages(
            db, conversation.id, question, answer, citations
        )
    except Exception:
        logger.exception("failed_to_save_chat_messages")
        yield f"event: error\ndata: {json.dumps({'detail': 'Failed to save conversation messages'})}\n\n"
        return

    # Yield done event
    total_tokens = input_tokens + output_tokens
    yield f"event: done\ndata: {json.dumps({'message_id': str(assistant_msg.id), 'total_tokens': total_tokens})}\n\n"

    # 6. Usage Logging (fire and forget/log failure but don't crash stream)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    await write_usage_log(
        db,
        actor.id,
        workspace_id,
        conversation.id,
        settings.gemini_generation_model,
        input_tokens,
        output_tokens,
        latency_ms,
    )
