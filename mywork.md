-uv init
-uv venv

- cai dependencies
uv add fastapi "uvicorn[standard]" pydantic-settings
uv add "sqlalchemy[asyncio]" asyncpg alembic
uv add redis
uv add structlog
uv add --dev pytest pytest-asyncio httpx : --dev = chỉ dùng khi develop / test, không cần khi deploy product
uv add --dev ruff mypy :lint/type check

-uv sync