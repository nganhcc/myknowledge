import redis.asyncio as aioredis

from app.core.config import settings

DOCUMENT_QUEUE_KEY = "document_processing_queue"

# queueing process_document id to redis queue
async def enqueue_document_processing(document_id: str) -> None:
    """Đẩy ID tài liệu vào hàng đợi Redis để xử lý bất đồng bộ."""
    # Tạo connection từ pool và đóng sau khi đẩy tin nhắn
    client = aioredis.from_url(settings.redis_url)
    try:
        await client.rpush(DOCUMENT_QUEUE_KEY, document_id)
    finally:
        await client.aclose()
