from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    filename: str
    mime_type: str
    size: int
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    retry_count: int

    model_config = ConfigDict(from_attributes=True)
