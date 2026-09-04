from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base"
    environment: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_base"
    )
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_key_prefix: str = "rate-limit"
    chat_rate_limit: int = 20
    upload_rate_limit: int = 10
    rate_limit_window_seconds: int = 60
    retrieval_cache_enabled: bool = True
    retrieval_cache_ttl_seconds: int = 300
    retrieval_cache_key_prefix: str = "retrieval"

    gemini_api_key: str | None = None
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_generation_model: str = "gemini-3.6-flash"
    max_document_retries: int = 3
    retrieval_candidate_limit: int = 50
    retrieval_final_limit: int = 5
    retrieval_rrf_k: int = 60
    retrieval_fts_config: str = "simple"
    query_rewrite_history_limit: int = 6
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-base"

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
