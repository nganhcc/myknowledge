import hashlib
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.storage import BaseStorageService
from app.services.workspace import WorkspaceForbiddenError, get_workspace


class DocumentNotFoundError(Exception):
    """Tài liệu không tồn tại."""


async def get_document_by_hash(
    db: AsyncSession, workspace_id: uuid.UUID, content_hash: str
) -> Document | None:
    return await db.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.content_hash == content_hash,
        )
    )


async def create_document(
    db: AsyncSession,
    storage: BaseStorageService,
    actor: User,
    workspace_id: uuid.UUID,
    filename: str,
    file_content: bytes,
    mime_type: str,
) -> Document:
    # Xác thực workspace & quyền thành viên (MEMBER, ADMIN, OWNER)
    await get_workspace(db, actor, workspace_id)

    # Tính toán content_hash (SHA-256)
    content_hash = hashlib.sha256(file_content).hexdigest()

    # Kiểm tra trùng lặp
    existing = await get_document_by_hash(db, workspace_id, content_hash)
    if existing:
        if existing.status != DocumentStatus.FAILED:
            # Nếu tài liệu đã tồn tại và không bị lỗi, tái sử dụng (deduplication)
            return existing
        else:
            # Nếu tài liệu trước đó bị lỗi (FAILED), tiến hành xóa để thử lại
            await storage.delete_file(existing.storage_key)
            await db.delete(existing)
            await db.commit()

    # Upload file thông qua storage service
    storage_key = await storage.upload_file(
        file_content=file_content,
        file_name=filename,
        workspace_id=str(workspace_id),
    )

    # Tạo bản ghi Document mới với trạng thái PENDING
    doc = Document(
        workspace_id=workspace_id,
        title=filename,
        filename=filename,
        mime_type=mime_type,
        size=len(file_content),
        status=DocumentStatus.PENDING,
        storage_key=storage_key,
        content_hash=content_hash,
        created_by=actor.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID
) -> Sequence[Document]:
    # Xác thực quyền thành viên
    await get_workspace(db, actor, workspace_id)

    result = await db.execute(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at)
    )
    return result.scalars().all()


async def get_document(
    db: AsyncSession,
    actor: User,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    # Xác thực quyền thành viên
    await get_workspace(db, actor, workspace_id)

    doc = await db.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace_id:
        raise DocumentNotFoundError()

    return doc


async def delete_document(
    db: AsyncSession,
    storage: BaseStorageService,
    actor: User,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    # Xác thực quyền thành viên & lấy role của actor
    _, role = await get_workspace(db, actor, workspace_id)

    doc = await db.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace_id:
        raise DocumentNotFoundError()

    # Chỉ người tạo tệp, ADMIN hoặc OWNER mới được quyền xóa tài liệu
    from app.models.membership import WorkspaceRole

    if doc.created_by != actor.id and role not in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
    }:
        raise WorkspaceForbiddenError()

    # Xóa file vật lý và bản ghi DB
    await storage.delete_file(doc.storage_key)
    await db.delete(doc)
    await db.commit()
