"""Pydantic schemas cho Workspaces & Members."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.membership import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WorkspaceResponse(BaseModel):
    """Workspace + role của chính user gọi API (để client tiện render)."""

    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    role: WorkspaceRole

    model_config = ConfigDict(from_attributes=True)


class MemberAdd(BaseModel):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class MemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: WorkspaceRole

    model_config = ConfigDict(from_attributes=True)

