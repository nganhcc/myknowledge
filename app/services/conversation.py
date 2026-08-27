import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.workspace import get_workspace


class ConversationNotFoundError(Exception):
    """Conversation not found or access denied."""
    pass


async def list_conversations(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID
) -> Sequence[Conversation]:
    """List all conversations in a workspace created by the current user."""
    # Verify workspace membership
    await get_workspace(db, actor, workspace_id)

    stmt = (
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == actor.id,
        )
        .order_by(Conversation.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_conversation(
    db: AsyncSession, actor: User, conversation_id: uuid.UUID
) -> Conversation:
    """Retrieve a conversation and verify workspace membership and user ownership."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != actor.id:
        raise ConversationNotFoundError("Conversation not found")

    # Verify workspace membership
    await get_workspace(db, actor, conversation.workspace_id)
    return conversation


async def list_messages(
    db: AsyncSession, actor: User, conversation_id: uuid.UUID
) -> Sequence[Message]:
    """Retrieve all messages in a conversation, ensuring authorization."""
    # Reuse authorization logic in get_conversation
    await get_conversation(db, actor, conversation_id)

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
