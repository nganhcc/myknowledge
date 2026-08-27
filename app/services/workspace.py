"""Business logic cho Workspaces: CRUD + phân quyền theo role membership.

Quyền tối thiểu theo từng thao tác:
- đọc / xem members       : MEMBER
- đổi tên / thêm member   : ADMIN (chỉ OWNER cấp được role != MEMBER)
- xoá workspace / đổi role: OWNER
- xoá member              : ADMIN (chỉ xoá MEMBER) hoặc OWNER (xoá cả ADMIN/OWNER)

Invariant quan trọng nhất: không bao giờ để workspace mất OWNER cuối cùng
(LastOwnerError) — kiểm tra count OWNER trước khi demote/remove.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import WorkspaceMember, WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import (
    MemberAdd,
    MemberResponse,
    WorkspaceCreate,
    WorkspaceUpdate,
)


class WorkspaceNotFoundError(Exception):
    """Workspace không tồn tại."""


class NotWorkspaceMemberError(Exception):
    """Caller không phải thành viên của workspace."""


class WorkspaceForbiddenError(Exception):
    """Là thành viên nhưng role không đủ quyền cho thao tác."""


class MemberNotFoundError(Exception):
    """User không phải thành viên của workspace (hoặc không tồn tại)."""


class UserNotFoundError(Exception):
    """Không tìm thấy user với email chỉ định."""

    def __init__(self, email: str) -> None:
        super().__init__(f"user not found: {email}")
        self.email = email


class AlreadyMemberError(Exception):
    """User đã là thành viên của workspace."""

    def __init__(self, email: str) -> None:
        super().__init__(f"user is already a member: {email}")
        self.email = email


class LastOwnerError(Exception):
    """Thao tác sẽ khiến workspace mất OWNER cuối cùng."""


async def _get_membership_role(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceRole | None:
    return await db.scalar(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


async def _count_owners(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
        )
        or 0
    )


async def _require_member(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Workspace, WorkspaceRole]:
    """Load workspace + role của caller.

    Non-member nhận NotWorkspaceMemberError để router trả 404 (che sự tồn tại
    của workspace khỏi người ngoài).
    """
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError()

    role = await _get_membership_role(db, workspace_id, user_id)
    if role is None:
        raise NotWorkspaceMemberError()
    return workspace, role


def _ensure_role(role: WorkspaceRole, allowed: set[WorkspaceRole]) -> None:
    if role not in allowed:
        raise WorkspaceForbiddenError()


async def create_workspace(
    db: AsyncSession, owner: User, payload: WorkspaceCreate
) -> Workspace:
    """Tạo workspace và gán creator làm OWNER trong cùng một transaction."""
    workspace = Workspace(name=payload.name.strip(), created_by=owner.id)
    db.add(workspace)
    await db.flush()  # cần workspace.id trước khi tạo membership
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.OWNER
        )
    )
    await db.commit()
    await db.refresh(workspace)
    return workspace


async def list_workspaces(
    db: AsyncSession, user: User
) -> list[tuple[Workspace, WorkspaceRole]]:
    """Chỉ các workspace mà user là thành viên, kèm role của user."""
    rows = await db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at)
    )
    return [(workspace, role) for workspace, role in rows.all()]


async def get_workspace(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID
) -> tuple[Workspace, WorkspaceRole]:
    return await _require_member(db, workspace_id, actor.id)


async def update_workspace(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID, payload: WorkspaceUpdate
) -> tuple[Workspace, WorkspaceRole]:
    workspace, role = await _require_member(db, workspace_id, actor.id)
    _ensure_role(role, {WorkspaceRole.ADMIN, WorkspaceRole.OWNER})

    workspace.name = payload.name.strip()
    await db.commit()
    await db.refresh(workspace)
    return workspace, role


async def delete_workspace(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID
) -> None:
    workspace, role = await _require_member(db, workspace_id, actor.id)
    _ensure_role(role, {WorkspaceRole.OWNER})

    # Memberships/documents cascade ở DB level (ondelete=CASCADE)
    await db.delete(workspace)
    await db.commit()


async def list_members(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID
) -> list[MemberResponse]:
    await _require_member(db, workspace_id, actor.id)

    rows = await db.execute(
        select(
            User.id.label("user_id"),
            User.email,
            User.name,
            WorkspaceMember.role,
        )
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
    )
    return [
        MemberResponse(
            user_id=row.user_id, email=row.email, name=row.name, role=row.role
        )
        for row in rows.all()
    ]


async def add_member(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID, payload: MemberAdd
) -> MemberResponse:
    _, actor_role = await _require_member(db, workspace_id, actor.id)
    _ensure_role(actor_role, {WorkspaceRole.ADMIN, WorkspaceRole.OWNER})

    # Chỉ OWNER được cấp role != MEMBER cho người khác
    if payload.role != WorkspaceRole.MEMBER and actor_role != WorkspaceRole.OWNER:
        raise WorkspaceForbiddenError()

    target = await db.scalar(select(User).where(User.email == payload.email))
    if target is None:
        raise UserNotFoundError(payload.email)

    if await _get_membership_role(db, workspace_id, target.id) is not None:
        raise AlreadyMemberError(payload.email)

    db.add(
        WorkspaceMember(workspace_id=workspace_id, user_id=target.id, role=payload.role)
    )
    await db.commit()
    return MemberResponse(
        user_id=target.id, email=target.email, name=target.name, role=payload.role
    )


async def update_member_role(
    db: AsyncSession,
    actor: User,
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: WorkspaceRole,
) -> MemberResponse:
    """Chỉ OWNER được đổi role; cấm hạ quyền OWNER cuối cùng."""
    _, actor_role = await _require_member(db, workspace_id, actor.id)
    _ensure_role(actor_role, {WorkspaceRole.OWNER})

    target = await db.get(User, target_user_id)
    target_role = (
        await _get_membership_role(db, workspace_id, target_user_id)
        if target is not None
        else None
    )
    if target is None or target_role is None:
        raise MemberNotFoundError()

    if (
        target_role == WorkspaceRole.OWNER
        and new_role != WorkspaceRole.OWNER
        and await _count_owners(db, workspace_id) <= 1
    ):
        raise LastOwnerError()

    membership = await db.get(
        WorkspaceMember, {"workspace_id": workspace_id, "user_id": target_user_id}
    )
    if membership is None:
        raise MemberNotFoundError()

    membership.role = new_role
    await db.commit()
    return MemberResponse(
        user_id=target.id, email=target.email, name=target.name, role=new_role
    )


async def remove_member(
    db: AsyncSession, actor: User, workspace_id: uuid.UUID, target_user_id: uuid.UUID
) -> None:
    """ADMIN chỉ xoá được MEMBER; OWNER xoá được cả ADMIN/OWNER.

    Không xoá được OWNER cuối cùng (kể cả owner tự xoá mình).
    """
    _, actor_role = await _require_member(db, workspace_id, actor.id)
    _ensure_role(actor_role, {WorkspaceRole.ADMIN, WorkspaceRole.OWNER})

    target = await db.get(User, target_user_id)
    target_role = (
        await _get_membership_role(db, workspace_id, target_user_id)
        if target is not None
        else None
    )
    if target is None or target_role is None:
        raise MemberNotFoundError()

    if target_role == WorkspaceRole.OWNER:
        if actor_role != WorkspaceRole.OWNER:
            raise WorkspaceForbiddenError()
        if await _count_owners(db, workspace_id) <= 1:
            raise LastOwnerError()
    elif actor_role == WorkspaceRole.ADMIN and target_role == WorkspaceRole.ADMIN:
        raise WorkspaceForbiddenError()

    membership = await db.get(
        WorkspaceMember, {"workspace_id": workspace_id, "user_id": target_user_id}
    )
    if membership is not None:
        await db.delete(membership)
    await db.commit()
