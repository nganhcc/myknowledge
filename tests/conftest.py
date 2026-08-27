import asyncio
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Phải set trước khi import app.*: engine/settings được dựng ngay tại thời điểm import.
# SECRET_KEY tối thiểu 32 bytes cho HS256 (RFC 7518)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-hs256-at-least-32-bytes")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_base_test",
)

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

# NullPool: mỗi connection tạo/đóng ngay khi dùng -> tránh lỗi "different event loop"
# khi app chạy trong event loop mới ở từng test.
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db

import app.db.session
app.db.session.async_session_factory = TestSession


def _run_alembic_upgrade() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


async def _ensure_test_database() -> None:
    """Tạo database test nếu chưa tồn tại (kết nối vào DB mặc định 'postgres')."""
    url = make_url(TEST_DATABASE_URL)
    if url.database is None:
        raise RuntimeError("DATABASE_URL thiếu tên database")
    conn = await asyncpg.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", url.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _truncate_all() -> None:
    tables = ", ".join(Base.metadata.tables)
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def pytest_sessionstart(session) -> None:
    asyncio.run(_ensure_test_database())
    _run_alembic_upgrade()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    """Xoá toàn bộ dữ liệu giữa các test để cô lập từng test."""
    yield
    asyncio.run(_truncate_all())


@pytest.fixture(autouse=True)
def mock_enqueue():
    """Mock Redis enqueueing to prevent connection errors during tests."""
    with patch("app.services.queue.enqueue_document_processing", AsyncMock()) as mock:
        yield mock