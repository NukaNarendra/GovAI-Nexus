import asyncio
import pytest
from typing import Dict, Any
from src.infrastructure.cache.redis_client import (
    RedisCacheManager,
    RateLimitExceeded,
    DistributedLockError,
)


@pytest.fixture
async def redis_manager(redis_url: str) -> RedisCacheManager:
    manager = RedisCacheManager(redis_url=redis_url)
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_redis_connection_and_ping(redis_manager: RedisCacheManager) -> None:
    is_connected = await redis_manager.ping()
    assert is_connected is True


@pytest.mark.asyncio
async def test_redis_set_get_delete_complex_data(
    redis_manager: RedisCacheManager,
) -> None:
    key = "test_complex_data_key"
    payload = {
        "status": "active",
        "nested": {"level1": {"level2": [1, 2, 3]}},
        "thresholds": [0.5, 0.75, 0.99],
    }

    await redis_manager.set(key, payload, ttl_seconds=60)

    retrieved = await redis_manager.get(key)
    assert retrieved is not None
    assert retrieved["status"] == "active"
    assert retrieved["nested"]["level1"]["level2"] == [1, 2, 3]

    exists = await redis_manager.exists(key)
    assert exists is True

    deleted = await redis_manager.delete(key)
    assert deleted is True

    retrieved_after_delete = await redis_manager.get(key)
    assert retrieved_after_delete is None


@pytest.mark.asyncio
async def test_redis_increment_functionality(redis_manager: RedisCacheManager) -> None:
    key = "test_counter_key"
    await redis_manager.delete(key)

    val1 = await redis_manager.increment(key, 1)
    assert val1 == 1

    val2 = await redis_manager.increment(key, 5)
    assert val2 == 6

    await redis_manager.delete(key)


@pytest.mark.asyncio
async def test_redis_fixed_window_rate_limiting(
    redis_manager: RedisCacheManager,
) -> None:
    identifier = "test_user_ip_127_0_0_1"
    max_reqs = 5
    window = 2

    for _ in range(max_reqs):
        allowed = await redis_manager.check_rate_limit(identifier, max_reqs, window)
        assert allowed is True

    with pytest.raises(RateLimitExceeded):
        await redis_manager.check_rate_limit(identifier, max_reqs, window)

    await asyncio.sleep(window + 0.1)

    allowed_again = await redis_manager.check_rate_limit(identifier, max_reqs, window)
    assert allowed_again is True


@pytest.mark.asyncio
async def test_redis_sliding_window_rate_limiting(
    redis_manager: RedisCacheManager,
) -> None:
    identifier = "api_key_sliding_test"
    max_reqs = 3
    window = 2

    for _ in range(max_reqs):
        allowed = await redis_manager.sliding_window_rate_limit(
            identifier, max_reqs, window
        )
        assert allowed is True
        await asyncio.sleep(0.1)

    with pytest.raises(RateLimitExceeded):
        await redis_manager.sliding_window_rate_limit(identifier, max_reqs, window)

    await asyncio.sleep(window)

    allowed_again = await redis_manager.sliding_window_rate_limit(
        identifier, max_reqs, window
    )
    assert allowed_again is True


@pytest.mark.asyncio
async def test_redis_distributed_locking_mechanism(
    redis_manager: RedisCacheManager,
) -> None:
    lock_name = "critical_financial_transaction_12345"

    lock_identifier = await redis_manager.acquire_lock(
        lock_name, acquire_timeout=2.0, lock_timeout=5.0
    )
    assert lock_identifier is not None

    with pytest.raises(DistributedLockError):
        await redis_manager.acquire_lock(
            lock_name, acquire_timeout=1.0, lock_timeout=5.0
        )

    released = await redis_manager.release_lock(lock_name, lock_identifier)
    assert released is True

    second_identifier = await redis_manager.acquire_lock(
        lock_name, acquire_timeout=2.0, lock_timeout=5.0
    )
    assert second_identifier is not None
    await redis_manager.release_lock(lock_name, second_identifier)


@pytest.mark.asyncio
async def test_redis_queue_operations(redis_manager: RedisCacheManager) -> None:
    queue_name = "webhook_processing_queue"

    await redis_manager.client.delete(
        redis_manager._generate_key(f"queue:{queue_name}")
    )

    payload1 = {"event": "tx_cleared", "id": 1}
    payload2 = {"event": "tx_failed", "id": 2}

    await redis_manager.push_to_queue(queue_name, payload1)
    await redis_manager.push_to_queue(queue_name, payload2)

    item1 = await redis_manager.pop_from_queue(queue_name)
    assert item1 == payload1

    item2 = await redis_manager.pop_from_queue(queue_name)
    assert item2 == payload2

    item3 = await redis_manager.pop_from_queue(queue_name, timeout=1)
    assert item3 is None
