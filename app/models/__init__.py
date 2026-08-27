"""Tất cả models — import tại đây để đăng ký vào Base.metadata.

Lưu ý: KHÔNG import các model trong `app/db/base.py` vì gây circular import
khi app.main -> api.deps -> models.user -> db.base -> models.user (partial import).
"""

from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.membership import WorkspaceMember
from app.models.message import Message, MessageRole
from app.models.user import User
from app.models.usage_log import UsageLog
from app.models.workspace import Workspace

__all__ = [
    "Conversation",
    "Document",
    "DocumentChunk",
    "Message",
    "MessageRole",
    "UsageLog",
    "User",
    "Workspace",
    "WorkspaceMember",
]