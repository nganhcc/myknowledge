"""Documents API endpoints: upload, list, get details, and delete documents.

Includes validation, error mappings to HTTP statuses, and permission checks.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_storage_service
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentStatusResponse
from app.services import document as document_service
from app.services import workspace as workspace_service
from app.services.storage import BaseStorageService

router = APIRouter(prefix=f"{settings.api_v1_prefix}/workspaces", tags=["documents"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
StorageDep = Annotated[BaseStorageService, Depends(get_storage_service)]


def _ws_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
    )


def _doc_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
    )


@router.post(
    "/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    workspace_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
    storage: StorageDep,
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    try:
        content = await file.read()
        filename = file.filename or "unnamed"
        mime_type = file.content_type or "application/octet-stream"

        doc = await document_service.create_document(
            db=db,
            storage=storage,
            actor=current_user,
            workspace_id=workspace_id,
            filename=filename,
            file_content=content,
            mime_type=mime_type,
        )

        # Chỉ đẩy vào queue xử lý nếu là tài liệu mới (PENDING)
        from app.models.document import DocumentStatus

        if doc.status == DocumentStatus.PENDING:
            from app.services.queue import enqueue_document_processing

            await enqueue_document_processing(str(doc.id))

    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None

    return DocumentResponse.model_validate(doc)


@router.get("/{workspace_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    workspace_id: uuid.UUID, current_user: UserDep, db: DbDep
) -> list[DocumentResponse]:
    try:
        docs = await document_service.list_documents(
            db=db, actor=current_user, workspace_id=workspace_id
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None

    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get(
    "/{workspace_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> DocumentResponse:
    try:
        doc = await document_service.get_document(
            db=db,
            actor=current_user,
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except document_service.DocumentNotFoundError:
        raise _doc_not_found() from None

    return DocumentResponse.model_validate(doc)


@router.get(
    "/{workspace_id}/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> DocumentStatusResponse:
    try:
        doc = await document_service.get_document(
            db=db,
            actor=current_user,
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except document_service.DocumentNotFoundError:
        raise _doc_not_found() from None

    return DocumentStatusResponse.model_validate(doc)


@router.delete(
    "/{workspace_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
    storage: StorageDep,
) -> None:
    try:
        await document_service.delete_document(
            db=db,
            storage=storage,
            actor=current_user,
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except document_service.DocumentNotFoundError:
        raise _doc_not_found() from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None
