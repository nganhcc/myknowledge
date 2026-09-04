import uuid
from typing import Self
from unittest.mock import patch

import pytest
from app.services.rate_limit import RateLimitExceeded, check_rate_limit


class FakePipeline:
    def __init__(self, client: "FakeRedis") -> None:
        self.client = client
        self.commands: list[tuple[str, str, int | None]] = []

    def incr(self, key: str) -> None:
        self.commands.append(("incr", key, None))

    def expire(self, key: str, seconds: int) -> None:
        self.commands.append(("expire", key, seconds))

    async def execute(self) -> list[int | bool]:
        results: list[int | bool] = []
        for command, key, value in self.commands:
            if command == "incr":
                self.client.counts[key] = self.client.counts.get(key, 0) + 1
                results.append(self.client.counts[key])
            else:
                self.client.ttls[key] = value or 0
                results.append(True)
        return results

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self)

    async def ttl(self, key: str) -> int:
        return self.ttls[key]

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


async def _check(
    fake_redis: FakeRedis,
    *,
    user_id: str,
    endpoint: str,
    limit: int,
    now: float,
) -> None:
    with patch(
        "app.services.rate_limit.aioredis.from_url", return_value=fake_redis
    ):
        await check_rate_limit(
            endpoint=endpoint,
            user_id=uuid.UUID(user_id),
            limit=limit,
            now=now,
        )


@pytest.mark.asyncio
async def test_new_fixed_window_allows_requests_again(fake_redis: FakeRedis) -> None:
    user_id = "00000000-0000-0000-0000-000000000001"

    await _check(fake_redis, user_id=user_id, endpoint="chat", limit=2, now=59.9)
    await _check(fake_redis, user_id=user_id, endpoint="chat", limit=2, now=59.99)
    await _check(fake_redis, user_id=user_id, endpoint="chat", limit=2, now=60.0)


@pytest.mark.asyncio
async def test_limit_returns_retry_information(fake_redis: FakeRedis) -> None:
    user_id = "00000000-0000-0000-0000-000000000002"

    await _check(fake_redis, user_id=user_id, endpoint="upload", limit=1, now=10.0)

    with pytest.raises(RateLimitExceeded) as error:
        await _check(
            fake_redis, user_id=user_id, endpoint="upload", limit=1, now=20.0
        )

    assert error.value.retry_after_seconds == 40


@pytest.mark.asyncio
async def test_users_have_separate_windows(fake_redis: FakeRedis) -> None:
    await _check(
        fake_redis,
        user_id="00000000-0000-0000-0000-000000000003",
        endpoint="chat",
        limit=1,
        now=10.0,
    )
    await _check(
        fake_redis,
        user_id="00000000-0000-0000-0000-000000000004",
        endpoint="chat",
        limit=1,
        now=10.0,
    )


@pytest.mark.asyncio
async def test_endpoints_have_separate_windows(fake_redis: FakeRedis) -> None:
    user_id = "00000000-0000-0000-0000-000000000005"

    await _check(fake_redis, user_id=user_id, endpoint="chat", limit=1, now=10.0)
    await _check(fake_redis, user_id=user_id, endpoint="upload", limit=1, now=10.0)
