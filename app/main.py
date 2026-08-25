from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.v1 import auth
from app.core.logging import setup_logging

# Khởi tạo structlog logger
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging ngay khi app bắt đầu
    setup_logging(json_logs=False)  # Để True nếu muốn dạng JSON
    logger.info("application_started", env="development", version="0.1.0")
    yield


app = FastAPI(
    title="Core API Services",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)


@app.get("/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    logger.info("health_check_called", status="ok")
    return {"status": "ok"}