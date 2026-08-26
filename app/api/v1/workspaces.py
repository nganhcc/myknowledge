"""Workspace & member management endpoints.

Routers mỏng: DI + gọi service + map domain exception -> HTTP status.
Non-member nhận 404 (không phải 403) để che sự tồn tại của workspace.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.membership import WorkspaceRole
from app.models.user import User
from app.schemas.workspace import (
    MemberAdd,
    MemberResponse,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services import workspace as workspace_service

router = APIRouter(prefix=f"{settings.api_v1_prefix}/workspaces", tags=["workspaces"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


def _ws_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
    )


@router.post(
    "", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED
)
async def create_workspace(
    payload: WorkspaceCreate, current_user: UserDep, db: DbDep
) -> WorkspaceResponse:
    workspace = await workspace_service.create_workspace(db, current_user, payload)
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        role=WorkspaceRole.OWNER,  # creator luôn là OWNER
    )


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(current_user: UserDep, db: DbDep) -> list[WorkspaceResponse]:
    rows = await workspace_service.list_workspaces(db, current_user)
    return [
        WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            created_by=workspace.created_by,
            created_at=workspace.created_at,
            role=role,
        )
        for workspace, role in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID, current_user: UserDep, db: DbDep
) -> WorkspaceResponse:
    try:
        workspace, role = await workspace_service.get_workspace(
            db, current_user, workspace_id
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        # Non-member cũng nhận 404 để không leak sự tồn tại của workspace
        raise _ws_not_found() from None

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        role=role,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    current_user: UserDep,
    db: DbDep,
) -> WorkspaceResponse:
    try:
        workspace, role = await workspace_service.update_workspace(
            db, current_user, workspace_id, payload
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        role=role,
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: uuid.UUID, current_user: UserDep, db: DbDep
) -> None:
    try:
        await workspace_service.delete_workspace(db, current_user, workspace_id)
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None


@router.get(
    "/{workspace_id}/members", response_model=list[MemberResponse]
)
async def list_members(
    workspace_id: uuid.UUID, current_user: UserDep, db: DbDep
) -> list[MemberResponse]:
    try:
        return await workspace_service.list_members(db, current_user, workspace_id)
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: uuid.UUID, payload: MemberAdd, current_user: UserDep, db: DbDep
) -> MemberResponse:
    try:
        return await workspace_service.add_member(
            db, current_user, workspace_id, payload
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
    ):
        raise _ws_not_found() from None
    except workspace_service.UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with email: {exc.email}",
        ) from None
    except workspace_service.AlreadyMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already a member: {exc.email}",
        ) from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None


@router.patch(
    "/{workspace_id}/members/{user_id}", response_model=MemberResponse
)
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    current_user: UserDep,
    db: DbDep,
) -> MemberResponse:
    try:
        return await workspace_service.update_member_role(
            db, current_user, workspace_id, user_id, payload.role
        )
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
        workspace_service.MemberNotFoundError,
    ):
        raise _ws_not_found() from None
    except workspace_service.LastOwnerError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote the last OWNER of the workspace",
        ) from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None


@router.delete(
    "/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    workspace_id: uuid.UUID, user_id: uuid.UUID, current_user: UserDep, db: DbDep
) -> None:
    try:
        await workspace_service.remove_member(db, current_user, workspace_id, user_id)
    except (
        workspace_service.WorkspaceNotFoundError,
        workspace_service.NotWorkspaceMemberError,
        workspace_service.MemberNotFoundError,
    ):
        raise _ws_not_found() from None
    except workspace_service.LastOwnerError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last OWNER of the workspace",
        ) from None
    except workspace_service.WorkspaceForbiddenError:
        raise _forbidden() from None




