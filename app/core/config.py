from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_base"
    redis_url: str = "redis://localhost:6379/0"

    gemini_api_key: str | None = None
    gemini_embedding_model: str = "text-embedding-004"
    max_document_retries: int = 3

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
# ignore[call-arg] là BẮT BUỘC: secret_key bắt buộc lúc runtime nhưng
# pydantic-settings không đưa vào signature mà mypy nhìn thấy.
# Đừng bỏ ignore này — đã thử và bị mypy báo "Missing named argument".