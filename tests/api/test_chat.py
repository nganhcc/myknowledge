import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.document import Document, DocumentStatus
from app.models.message import Message

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
WS_URL = "/api/v1/workspaces"
CHAT_URL = "/api/v1/chat"
VALID_PASSWORD = "password123"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_user(client: AsyncClient, email: str) -> dict[str, str]:
    reg = await client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": VALID_PASSWORD,
            "name": email.split("@")[0],
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post(
        LOGIN_URL, data={"username": email, "password": VALID_PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {
        "token": login.json()["access_token"],
        "id": reg.json()["id"],
        "email": email,
    }


async def _create_ws(client: AsyncClient, token: str, name: str = "My WS"):
    res = await client.post(WS_URL, json={"name": name}, headers=_auth(token))
    assert res.status_code == 201
    return res.json()["id"]


def parse_sse_events(lines: list[str]) -> list[tuple[str, Any]]:
    """Helper to parse SSE events from lines."""
    events = []
    current_event = None
    for line in lines:
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            data_val = json.loads(data_str)
            events.append((current_event, data_val))
    return events


@pytest.mark.asyncio
async def test_chat_streaming_and_history_success(client: AsyncClient) -> None:
    # 1. Setup user & workspace
    user1 = await _new_user(client, "user1@example.com")
    ws_id = await _create_ws(client, user1["token"])

    # 2. Insert dummy Document and DocumentChunk with embedding
    async with async_session_factory() as db:
        doc = Document(
            workspace_id=uuid.UUID(ws_id),
            title="Overview.txt",
            filename="Overview.txt",
            mime_type="text/plain",
            size=100,
            status=DocumentStatus.READY,
            storage_key="/storage/Overview.txt",
            content_hash="hash123",
            created_by=uuid.UUID(user1["id"]),
        )
        db.add(doc)
        await db.flush()

        chunk = DocumentChunk(
            document_id=doc.id,
            workspace_id=uuid.UUID(ws_id),
            chunk_index=0,
            content="FastAPI is a modern, fast (high-performance), web framework.",
            token_count=10,
            embedding=[0.1] * 768,
        )
        db.add(chunk)
        await db.commit()

    # 3. Mock embedding and streaming API calls
    mock_embed = AsyncMock(return_value=[[0.1] * 768])

    # Mock SSE response for Gemini API
    # Since httpx.AsyncClient.stream is a context manager, we need a special mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    # Simulate line-by-line streaming of SSE chunks from Gemini
    sse_lines = [
        b'data: {"candidates": [{"content": {"parts": [{"text": "FastAPI"}]}}]}',
        b'data: {"candidates": [{"content": {"parts": [{"text": " is"}]}}]}',
        b'data: {"candidates": [{"content": {"parts": [{"text": " fast."}]}}]}',
        b'data: {"usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5}}',
    ]
    
    async def aiter_lines() -> AsyncIterator[str]:
        for line in sse_lines:
            yield line.decode("utf-8")

    mock_response.aiter_lines = aiter_lines

    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc, tb):
            pass

    mock_stream = MagicMock(return_value=AsyncContextManagerMock())

    with (
        patch("app.core.config.settings.gemini_api_key", "test-api-key"),
        patch("app.services.chat.embed_texts", mock_embed),
        patch("httpx.AsyncClient.stream", mock_stream),
    ):
        # 4. Request streaming chat endpoint
        payload = {
            "workspace_id": ws_id,
            "message": "What is FastAPI?",
        }
        response = await client.post(CHAT_URL, json=payload, headers=_auth(user1["token"]))
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")

        # 5. Consume and parse the SSE stream
        lines = []
        async for line in response.aiter_lines():
            if line.strip():
                lines.append(line)

        events = parse_sse_events(lines)

        # 6. Verify SSE events structure
        assert len(events) >= 4
        
        # Verify conversation event
        assert events[0][0] == "conversation"
        assert "conversation_id" in events[0][1]
        conv_id = events[0][1]["conversation_id"]

        # Verify citations event
        assert events[1][0] == "citations"
        assert len(events[1][1]["citations"]) == 1
        assert events[1][1]["citations"][0]["document_name"] == "Overview.txt"

        # Verify token events
        token_events = [ev for ev in events if ev[0] == "token"]
        assert len(token_events) == 3
        assert token_events[0][1]["token"] == "FastAPI"
        assert token_events[1][1]["token"] == " is"
        assert token_events[2][1]["token"] == " fast."

        # Verify done event
        assert events[-1][0] == "done"
        assert "message_id" in events[-1][1]
        assert events[-1][1]["total_tokens"] == 25

    # 7. Check if messages were correctly saved in the DB
    async with async_session_factory() as db:
        messages = (
            await db.execute(
                pytest.importorskip("sqlalchemy").select(Message)
                .where(Message.conversation_id == uuid.UUID(conv_id))
                .order_by(Message.created_at.asc())
            )
        ).scalars().all()
        
        assert len(messages) == 2
        assert messages[0].role == "USER"
        assert messages[0].content == "What is FastAPI?"
        assert messages[1].role == "ASSISTANT"
        assert messages[1].content == "FastAPI is fast."
        assert len(messages[1].citations) == 1
        assert messages[1].citations[0]["document_name"] == "Overview.txt"

    # 8. Test list conversations endpoint
    list_conv_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=_auth(user1["token"]),
    )
    assert list_conv_res.status_code == 200
    conv_list = list_conv_res.json()
    assert len(conv_list) == 1
    assert conv_list[0]["id"] == conv_id

    # 9. Test get conversation detail endpoint
    get_conv_res = await client.get(
        f"/api/v1/conversations/{conv_id}",
        headers=_auth(user1["token"]),
    )
    assert get_conv_res.status_code == 200
    assert get_conv_res.json()["title"] == "What is FastAPI?"

    # 10. Test list messages history endpoint
    msg_history_res = await client.get(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=_auth(user1["token"]),
    )
    assert msg_history_res.status_code == 200
    history = msg_history_res.json()
    assert len(history) == 2
    assert history[0]["content"] == "What is FastAPI?"
    assert history[1]["content"] == "FastAPI is fast."
    assert history[1]["citations"][0]["document_name"] == "Overview.txt"


@pytest.mark.asyncio
async def test_chat_workspace_isolation(client: AsyncClient) -> None:
    # Setup two users
    user1 = await _new_user(client, "alice@example.com")
    user2 = await _new_user(client, "bob@example.com")

    # Create workspace for user1
    ws_id = await _create_ws(client, user1["token"])

    # Bob tries to query user1's workspace
    payload = {
        "workspace_id": ws_id,
        "message": "Hello Alice's workspace?",
    }
    
    with patch("app.core.config.settings.gemini_api_key", "test-api-key"):
        # Bob should get error or forbidden
        response = await client.post(CHAT_URL, json=payload, headers=_auth(user2["token"]))
        assert response.status_code == 200
        
        # Bob consumes the stream - it should stream an error event containing "Workspace access denied" or "Workspace not found"
        lines = []
        async for line in response.aiter_lines():
            if line.strip():
                lines.append(line)
                
        events = parse_sse_events(lines)
        assert len(events) == 1
        assert events[0][0] == "error"
        assert "Workspace access denied" in events[0][1]["detail"]
