import asyncio
import signal
import uuid

import redis.asyncio as aioredis
import structlog

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.document import process_document
from app.services.queue import DOCUMENT_QUEUE_KEY
from app.services.storage import LocalStorageService

logger = structlog.get_logger()

# Cờ để quản lý tắt worker an toàn (graceful shutdown)
shutdown_event = asyncio.Event()


def signal_handler() -> None:
    logger.info("worker_shutdown_signal_received")
    shutdown_event.set()


async def worker_loop() -> None:
    logger.info(
        "worker_started",
        queue=DOCUMENT_QUEUE_KEY,
        redis_url=settings.redis_url,
    )

    redis_client = aioredis.from_url(settings.redis_url)
    storage = LocalStorageService()

    # Đăng ký signal handler để xử lý tắt tiến trình (SIGINT, SIGTERM)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Môi trường như Windows có thể không hỗ trợ signal handler
            pass

    while not shutdown_event.is_set():
        try:
            # Block tối đa 1 giây chờ tin nhắn từ queue để tránh CPU loop 100%
            result = await redis_client.brpop(DOCUMENT_QUEUE_KEY, timeout=1)
            if result:
                _, doc_id_bytes = result
                doc_id_str = (
                    doc_id_bytes.decode("utf-8")
                    if isinstance(doc_id_bytes, bytes)
                    else doc_id_bytes
                )
                document_id = uuid.UUID(doc_id_str)

                logger.info("worker_job_received", document_id=document_id)

                # Mỗi công việc chạy trong một DB session độc lập
                async with async_session_factory() as db:
                    await process_document(db, storage, document_id)

                logger.info("worker_job_completed", document_id=document_id)
        except asyncio.CancelledError:
            logger.info("worker_loop_cancelled")
            break
        except Exception as e:  # noqa: BLE001
            logger.error("worker_job_error", error=str(e))
            # Tránh spam log liên tục khi có lỗi nghiêm trọng (như mất kết nối DB)
            await asyncio.sleep(2)

    # Đóng kết nối Redis trước khi thoát hẳn
    await redis_client.aclose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    from app.core.logging import setup_logging

    setup_logging(json_logs=settings.environment == "production")
    
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("worker_interrupted_by_user")
