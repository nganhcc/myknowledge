import math
import time
import uuid

import redis.asyncio as aioredis

from app.core.config import settings


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Rate limit exceeded")


def _window_key(endpoint: str, user_id: uuid.UUID, window: int) -> str:
    return f"{settings.rate_limit_key_prefix}:{endpoint}:{user_id}:{window}"


async def check_rate_limit(
    *,
    endpoint: str,
    user_id: uuid.UUID,
    limit: int,
    now: float | None = None,
) -> None:
    current_time = time.time() if now is None else now
    window_seconds = settings.rate_limit_window_seconds
    window = math.floor(current_time / window_seconds)
    window_end = (window + 1) * window_seconds
    key = _window_key(endpoint, user_id, window)

    client = aioredis.from_url(settings.redis_url)
    try:
        async with client.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, max(1, math.ceil(window_end - current_time)))
            count, _ = await pipeline.execute()

        if count > limit:
            retry_after = await client.ttl(key)
            raise RateLimitExceeded(max(1, retry_after))
    finally:
        await client.aclose()