import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

VALID_PASSWORD = "password123"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = VALID_PASSWORD,
    name: str = "Test User",
):
    return await client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "name": name},
    )


async def _login(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = VALID_PASSWORD,
):
    return await client.post(
        LOGIN_URL,
        data={"username": email, "password": password},
    )


async def test_register_creates_user(client: AsyncClient) -> None:
    response = await _register(client)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["name"] == "Test User"
    assert uuid.UUID(data["id"])  # id là UUID hợp lệ
    assert "created_at" in data
    assert "password" not in data


async def test_register_duplicate_email_returns_400(client: AsyncClient) -> None:
    await _register(client)
    response = await _register(client)

    assert response.status_code == 400


async def test_register_invalid_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        REGISTER_URL,
        json={"email": "user@example.com", "password": "short", "name": ""},
    )

    assert response.status_code == 422


async def test_login_returns_access_token(client: AsyncClient) -> None:
    await _register(client)
    response = await _login(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await _register(client)
    response = await _login(client, password="wrong-password")

    assert response.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await _login(client, email="nobody@example.com")

    assert response.status_code == 401


async def test_me_with_valid_token_returns_user(client: AsyncClient) -> None:
    registered = await _register(client)
    token = (await _login(client)).json()["access_token"]

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["id"] == registered.json()["id"]


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(ME_URL)

    assert response.status_code == 401


async def test_me_with_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        ME_URL, headers={"Authorization": "Bearer not-a-valid-token"}
    )

    assert response.status_code == 401