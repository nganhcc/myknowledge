import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
WS_URL = "/api/v1/workspaces"
VALID_PASSWORD = "password123"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _add_and_promote(
    client: AsyncClient, owner_token: str, ws_id: str, user: dict[str, str]
) -> None:
    """Thêm user vào workspace (MEMBER) rồi thăng lên ADMIN.

    Đổi role chỉ áp dụng cho thành viên hiện có — thêm trước, thăng sau.
    """
    added = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": user["email"]},
        headers=_auth(owner_token),
    )
    assert added.status_code == 201, added.text
    promoted = await client.patch(
        f"{WS_URL}/{ws_id}/members/{user['id']}",
        json={"role": "ADMIN"},
        headers=_auth(owner_token),
    )
    assert promoted.status_code == 200, promoted.text


async def _new_user(
    client: AsyncClient, email: str
) -> dict[str, str]:
    """Đăng ký + đăng nhập, trả về token và user id."""
    reg = await client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": VALID_PASSWORD,
            "name": email.split("@")[0],
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post(
        LOGIN_URL, data={"username": email, "password": VALID_PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {
        "token": login.json()["access_token"],
        "id": reg.json()["id"],
        "email": email,
    }


async def _create_ws(client: AsyncClient, token: str, name: str = "My WS"):
    return await client.post(WS_URL, json={"name": name}, headers=_auth(token))


async def test_create_workspace_requires_auth(client: AsyncClient) -> None:
    response = await client.post(WS_URL, json={"name": "No Token WS"})

    assert response.status_code == 401


async def test_create_workspace_returns_owner_role(client: AsyncClient) -> None:
    user = await _new_user(client, "owner@example.com")

    response = await _create_ws(client, user["token"])

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My WS"
    assert data["created_by"] == user["id"]
    assert data["role"] == "OWNER"
    uuid.UUID(data["id"])


async def test_get_workspace_member_ok_outsider_404(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    outsider = await _new_user(client, "outsider@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    ok = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(owner["token"]))
    hidden = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(outsider["token"]))

    assert ok.status_code == 200
    assert ok.json()["role"] == "OWNER"
    # Non-member nhận 404 (không phải 403) để che sự tồn tại của workspace
    assert hidden.status_code == 404


async def test_list_returns_only_own_workspaces(client: AsyncClient) -> None:
    alice = await _new_user(client, "alice@example.com")
    bob = await _new_user(client, "bob@example.com")
    await _create_ws(client, alice["token"], "Alice WS 1")
    await _create_ws(client, alice["token"], "Alice WS 2")
    await _create_ws(client, bob["token"], "Bob WS")

    alice_list = await client.get(WS_URL, headers=_auth(alice["token"]))
    bob_list = await client.get(WS_URL, headers=_auth(bob["token"]))

    assert [ws["name"] for ws in alice_list.json()] == ["Alice WS 1", "Alice WS 2"]
    assert [ws["name"] for ws in bob_list.json()] == ["Bob WS"]
    assert all(ws["role"] == "OWNER" for ws in alice_list.json())


async def test_rename_by_outsider_returns_404(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    outsider = await _new_user(client, "outsider@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    response = await client.patch(
        f"{WS_URL}/{ws_id}",
        json={"name": "Hacked"},
        headers=_auth(outsider["token"]),
    )

    assert response.status_code == 404


async def test_rename_admin_ok_member_forbidden(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    admin = await _new_user(client, "admin@example.com")
    member = await _new_user(client, "member@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    # Owner thêm + thăng admin lên ADMIN; thêm member (role MEMBER mặc định)
    await _add_and_promote(client, owner["token"], ws_id, admin)
    added = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": member["email"]},
        headers=_auth(owner["token"]),
    )
    assert added.status_code == 201, added.text

    renamed_by_admin = await client.patch(
        f"{WS_URL}/{ws_id}",
        json={"name": "Renamed by Admin"},
        headers=_auth(admin["token"]),
    )
    forbidden = await client.patch(
        f"{WS_URL}/{ws_id}",
        json={"name": "Renamed by Member"},
        headers=_auth(member["token"]),
    )

    assert renamed_by_admin.status_code == 200
    assert renamed_by_admin.json()["name"] == "Renamed by Admin"
    assert forbidden.status_code == 403


async def test_delete_by_owner_then_gone(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    deleted = await client.delete(f"{WS_URL}/{ws_id}", headers=_auth(owner["token"]))
    gone = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(owner["token"]))
    empty_list = await client.get(WS_URL, headers=_auth(owner["token"]))

    assert deleted.status_code == 204
    assert gone.status_code == 404
    assert empty_list.json() == []


async def test_delete_forbidden_for_non_owner(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    admin = await _new_user(client, "admin@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]
    await _add_and_promote(client, owner["token"], ws_id, admin)

    response = await client.delete(
        f"{WS_URL}/{ws_id}", headers=_auth(admin["token"])
    )
    still_there = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(owner["token"]))

    # ADMIN đủ cao để đổi tên nhưng không được xoá workspace
    assert response.status_code == 403
    assert still_there.status_code == 200


async def test_add_member_and_access_granted(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    member = await _new_user(client, "member@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    added = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": member["email"]},
        headers=_auth(owner["token"]),
    )
    members = await client.get(
        f"{WS_URL}/{ws_id}/members", headers=_auth(owner["token"])
    )
    member_view = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(member["token"]))

    assert added.status_code == 201
    assert added.json()["role"] == "MEMBER"
    roles = {m["email"]: m["role"] for m in members.json()}
    assert roles == {owner["email"]: "OWNER", member["email"]: "MEMBER"}
    # Member mới truy cập được workspace ngay
    assert member_view.status_code == 200
    assert member_view.json()["role"] == "MEMBER"


async def test_add_duplicate_and_unknown_email(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    unknown = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": "ghost@example.com"},
        headers=_auth(owner["token"]),
    )
    duplicate = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": owner["email"]},
        headers=_auth(owner["token"]),
    )

    assert unknown.status_code == 404
    assert duplicate.status_code == 400


async def test_admin_cannot_grant_admin_role(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    admin = await _new_user(client, "admin@example.com")
    candidate = await _new_user(client, "candidate@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]
    await _add_and_promote(client, owner["token"], ws_id, admin)

    response = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": candidate["email"], "role": "ADMIN"},
        headers=_auth(admin["token"]),
    )
    ok_as_member = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": candidate["email"], "role": "MEMBER"},
        headers=_auth(admin["token"]),
    )

    # ADMIN chỉ thêm được MEMBER; cấp ADMIN là việc của OWNER
    assert response.status_code == 403
    assert ok_as_member.status_code == 201


async def test_change_role_requires_owner(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    admin = await _new_user(client, "admin@example.com")
    member = await _new_user(client, "member@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]
    await _add_and_promote(client, owner["token"], ws_id, admin)
    added = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": member["email"]},
        headers=_auth(owner["token"]),
    )
    assert added.status_code == 201, added.text

    by_admin = await client.patch(
        f"{WS_URL}/{ws_id}/members/{member['id']}",
        json={"role": "ADMIN"},
        headers=_auth(admin["token"]),
    )
    by_owner = await client.patch(
        f"{WS_URL}/{ws_id}/members/{member['id']}",
        json={"role": "ADMIN"},
        headers=_auth(owner["token"]),
    )

    assert by_admin.status_code == 403
    assert by_owner.status_code == 200
    assert by_owner.json()["role"] == "ADMIN"


async def test_cannot_demote_or_remove_last_owner(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]

    demote_self = await client.patch(
        f"{WS_URL}/{ws_id}/members/{owner['id']}",
        json={"role": "MEMBER"},
        headers=_auth(owner["token"]),
    )
    remove_self = await client.delete(
        f"{WS_URL}/{ws_id}/members/{owner['id']}", headers=_auth(owner["token"])
    )

    assert demote_self.status_code == 400
    assert remove_self.status_code == 400
    # Owner vẫn nguyên quyền
    still_ok = await client.get(f"{WS_URL}/{ws_id}", headers=_auth(owner["token"]))
    assert still_ok.status_code == 200


async def test_remove_second_owner_is_allowed(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    co_owner = await _new_user(client, "co-owner@example.com")
    ws_id = (await _create_ws(client, owner["token"])).json()["id"]
    added = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": co_owner["email"], "role": "OWNER"},
        headers=_auth(owner["token"]),
    )
    assert added.status_code == 201

    removed = await client.delete(
        f"{WS_URL}/{ws_id}/members/{co_owner['id']}", headers=_auth(owner["token"])
    )
    lost_access = await client.get(
        f"{WS_URL}/{ws_id}", headers=_auth(co_owner["token"])
    )

    # Còn 2 OWNER nên xoá 1 người là hợp lệ
    assert removed.status_code == 204
    assert lost_access.status_code == 404


async def test_create_workspace_invalid_name_422(client: AsyncClient) -> None:
    user = await _new_user(client, "user@example.com")

    empty = await _create_ws(client, user["token"], name="")
    missing = await client.post(WS_URL, json={}, headers=_auth(user["token"]))

    assert empty.status_code == 422
    assert missing.status_code == 422



