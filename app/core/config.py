from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_base"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
# Sau, tat ca services se lay config tu: from app.core.config import settings

# pydantic-settings nạp secret_key từ env (SECRET_KEY), mypy không biết điều này
settings = Settings()  # type: ignore[call-arg]