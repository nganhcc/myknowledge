from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.main import app


@contextmanager
def client_context() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    with client_context() as c:
        yield c


def test_health_check_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}