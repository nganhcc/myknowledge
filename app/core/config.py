from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base"
    environment: str = "development"
    debug: bool = True

    database_url: str
    redis_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
# Sau, tat ca services se lay config tu: from app.core.config import settings

settings = Settings()  # type: ignore[call-arg]