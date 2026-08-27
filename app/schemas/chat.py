import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageRole


class ChatRequest(BaseModel):
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page: int | None

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[Citation]

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[Citation] | None
    token_count: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
