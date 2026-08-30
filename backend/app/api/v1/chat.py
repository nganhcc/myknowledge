import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ConversationResponse,
    MessageResponse,
)
from app.services import chat as chat_service
from app.services import conversation as conversation_service
from app.services import workspace as workspace_service

router = APIRouter(tags=["chat"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


def _ws_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
    )


def _conv_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
    )


@router.post(f"{settings.api_v1_prefix}/chat")
async def chat_stream(
    request: ChatRequest,
    current_user: UserDep,
    db: DbDep,
) -> StreamingResponse:
    """Stream chat response back to client using SSE."""
    return StreamingResponse(
        chat_service.chat_streaming(
            db=db,
            actor=current_user,
            workspace_id=request.workspace_id,
            conversation_id=request.conversation_id,
            question=request.message,
        ),
        media_type="text/event-stream",
    )


@router.get(
    f"{settings.api_v1_prefix}/workspaces/{{workspace_id}}/conversations",
    response_model=list[ConversationResponse],
)
async def list_conversations(
    workspace_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[ConversationResponse]:
    """Retrieve all conversations for the authenticated user within a workspace."""
    try:
        conversations = await conversation_service.list_conversations(
            db=db, actor=current_user, workspace_id=workspace_id
        )
        return [ConversationResponse.model_validate(c) for c in conversations]
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None


@router.get(
    f"{settings.api_v1_prefix}/conversations/{{conversation_id}}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> ConversationResponse:
    """Retrieve details of a single conversation."""
    try:
        conversation = await conversation_service.get_conversation(
            db=db, actor=current_user, conversation_id=conversation_id
        )
        return ConversationResponse.model_validate(conversation)
    except conversation_service.ConversationNotFoundError:
        raise _conv_not_found() from None
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None


@router.get(
    f"{settings.api_v1_prefix}/conversations/{{conversation_id}}/messages",
    response_model=list[MessageResponse],
)
async def list_messages(
    conversation_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[MessageResponse]:
    """Retrieve the full message history for a conversation."""
    try:
        messages = await conversation_service.list_messages(
            db=db, actor=current_user, conversation_id=conversation_id
        )
        return [MessageResponse.model_validate(m) for m in messages]
    except conversation_service.ConversationNotFoundError:
        raise _conv_not_found() from None
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
