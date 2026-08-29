from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, chat, documents, workspaces
from app.core.config import settings
from app.core.logging import setup_logging

# Khởi tạo structlog logger
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging ngay khi app bắt đầu; JSON log khi chạy production
    setup_logging(json_logs=settings.environment == "production")
    logger.info("application_started", env=settings.environment, version=app.version)
    yield


app = FastAPI(
    title="Core API Services",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    logger.info("health_check_called", status="ok")
    return {"status": "ok"}
