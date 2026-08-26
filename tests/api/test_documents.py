import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_storage_service
from app.db.session import get_db
from app.main import app
from app.models.document import Document, DocumentStatus
from app.services.storage import LocalStorageService

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
WS_URL = "/api/v1/workspaces"
VALID_PASSWORD = "password123"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_storage(tmp_path):
    # Override storage service to use a temp directory for tests
    temp_dir = tmp_path / "test_storage"
    temp_dir.mkdir()

    def override_get_storage_service():
        return LocalStorageService(base_dir=str(temp_dir))

    app.dependency_overrides[get_storage_service] = override_get_storage_service
    yield
    app.dependency_overrides.pop(get_storage_service, None)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_user(client: AsyncClient, email: str) -> dict[str, str]:
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
    res = await client.post(WS_URL, json={"name": name}, headers=_auth(token))
    assert res.status_code == 201
    return res.json()["id"]


async def _add_member(
    client: AsyncClient, owner_token: str, ws_id: str, email: str, role: str = "MEMBER"
) -> dict[str, str]:
    res = await client.post(
        f"{WS_URL}/{ws_id}/members",
        json={"email": email, "role": role},
        headers=_auth(owner_token),
    )
    assert res.status_code == 201
    return res.json()


async def test_upload_document_success(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = await _create_ws(client, owner["token"])

    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files,
        headers=_auth(owner["token"]),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["mime_type"] == "text/plain"
    assert data["size"] == 11
    assert data["status"] == "PENDING"
    assert "id" in data


async def test_upload_document_requires_membership(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    outsider = await _new_user(client, "outsider@example.com")
    ws_id = await _create_ws(client, owner["token"])

    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files,
        headers=_auth(outsider["token"]),
    )

    # Nhận 404 để che sự tồn tại của workspace với người ngoài
    assert response.status_code == 404


async def test_upload_deduplication(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = await _create_ws(client, owner["token"])

    files1 = {"file": ("test.txt", b"unique content", "text/plain")}
    res1 = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files1,
        headers=_auth(owner["token"]),
    )
    assert res1.status_code == 201
    doc_id_1 = res1.json()["id"]

    # Upload tệp tin có cùng nội dung lần 2
    files2 = {"file": ("test_another_name.txt", b"unique content", "text/plain")}
    res2 = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files2,
        headers=_auth(owner["token"]),
    )
    assert res2.status_code == 201
    doc_id_2 = res2.json()["id"]

    # Phải trả về cùng một bản ghi document (cùng ID)
    assert doc_id_1 == doc_id_2


async def test_upload_retry_failed_document(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = await _create_ws(client, owner["token"])

    # Upload lần 1
    files = {"file": ("test.txt", b"retry content", "text/plain")}
    res = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files,
        headers=_auth(owner["token"]),
    )
    assert res.status_code == 201
    doc_id_1 = res.json()["id"]

    # Giả lập trạng thái FAILED trong database
    async for db in get_db():
        doc = await db.get(Document, uuid.UUID(doc_id_1))
        assert doc is not None
        doc.status = DocumentStatus.FAILED
        await db.commit()
        break

    # Upload lại lần 2 cùng nội dung đó
    res2 = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files=files,
        headers=_auth(owner["token"]),
    )
    assert res2.status_code == 201
    doc_id_2 = res2.json()["id"]

    # Phải tạo ra bản ghi mới (khác ID)
    assert doc_id_1 != doc_id_2

    # Bản ghi cũ đã bị xóa
    async for db in get_db():
        old_doc = await db.get(Document, uuid.UUID(doc_id_1))
        assert old_doc is None
        break


async def test_list_documents(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = await _create_ws(client, owner["token"])

    await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("f1.txt", b"content 1", "text/plain")},
        headers=_auth(owner["token"]),
    )
    await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("f2.txt", b"content 2", "text/plain")},
        headers=_auth(owner["token"]),
    )

    response = await client.get(
        f"{WS_URL}/{ws_id}/documents",
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 2
    assert {d["filename"] for d in docs} == {"f1.txt", "f2.txt"}


async def test_get_document_details(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    ws_id = await _create_ws(client, owner["token"])

    uploaded = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("f1.txt", b"content", "text/plain")},
        headers=_auth(owner["token"]),
    )
    doc_id = uploaded.json()["id"]

    response = await client.get(
        f"{WS_URL}/{ws_id}/documents/{doc_id}",
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "f1.txt"


async def test_get_document_outsider_returns_404(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    outsider = await _new_user(client, "outsider@example.com")
    ws_id = await _create_ws(client, owner["token"])

    uploaded = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("f1.txt", b"content", "text/plain")},
        headers=_auth(owner["token"]),
    )
    doc_id = uploaded.json()["id"]

    # Outsider truy cập nhận 404
    response = await client.get(
        f"{WS_URL}/{ws_id}/documents/{doc_id}",
        headers=_auth(outsider["token"]),
    )
    assert response.status_code == 404


async def test_delete_document_permissions(client: AsyncClient) -> None:
    owner = await _new_user(client, "owner@example.com")
    member_a = await _new_user(client, "member_a@example.com")
    member_b = await _new_user(client, "member_b@example.com")

    ws_id = await _create_ws(client, owner["token"])
    await _add_member(client, owner["token"], ws_id, member_a["email"])
    await _add_member(client, owner["token"], ws_id, member_b["email"])

    # Member A upload document
    uploaded = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("a.txt", b"content A", "text/plain")},
        headers=_auth(member_a["token"]),
    )
    doc_id = uploaded.json()["id"]

    # 1. Member B (không phải owner/admin/creator) xóa thử -> 403 Forbidden
    forbidden_res = await client.delete(
        f"{WS_URL}/{ws_id}/documents/{doc_id}",
        headers=_auth(member_b["token"]),
    )
    assert forbidden_res.status_code == 403

    # 2. Member A (người tạo) tự xóa -> 204 No Content
    ok_res = await client.delete(
        f"{WS_URL}/{ws_id}/documents/{doc_id}",
        headers=_auth(member_a["token"]),
    )
    assert ok_res.status_code == 204

    # 3. Owner xóa document của người khác -> 204 No Content
    # Re-upload by member A
    uploaded2 = await client.post(
        f"{WS_URL}/{ws_id}/documents",
        files={"file": ("a.txt", b"content A", "text/plain")},
        headers=_auth(member_a["token"]),
    )
    doc_id2 = uploaded2.json()["id"]

    owner_del = await client.delete(
        f"{WS_URL}/{ws_id}/documents/{doc_id2}",
        headers=_auth(owner["token"]),
    )
    assert owner_del.status_code == 204
