import json
import time
import asyncio
from typing import Any, Optional, Dict, List, Union
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError


class CacheEngineError(Exception):
    pass


class RateLimitExceeded(CacheEngineError):
    pass


class DistributedLockError(CacheEngineError):
    pass


class RedisCacheManager:
    def __init__(self, redis_url: str, max_connections: int = 10, timeout: float = 2.0):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.timeout = timeout
        self.pool = redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=self.max_connections,
            decode_responses=True,
            socket_timeout=self.timeout,
        )
        self.client = redis.Redis(connection_pool=self.pool)
        self.prefix = "enterprise_gov:"

    def _generate_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except (ConnectionError, TimeoutError):
            return False

    async def get(self, key: str) -> Optional[Any]:
        try:
            full_key = self._generate_key(key)
            data = await self.client.get(full_key)
            if data is None:
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        except RedisError as e:
            raise CacheEngineError(f"Redis GET failed: {str(e)}")

    async def set(
        self, key: str, value: Any, ttl_seconds: Optional[int] = None
    ) -> bool:
        try:
            full_key = self._generate_key(key)
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)

            if ttl_seconds:
                return await self.client.setex(full_key, ttl_seconds, serialized_value)
            return await self.client.set(full_key, serialized_value)
        except RedisError as e:
            raise CacheEngineError(f"Redis SET failed: {str(e)}")

    async def delete(self, key: str) -> bool:
        try:
            full_key = self._generate_key(key)
            result = await self.client.delete(full_key)
            return result > 0
        except RedisError as e:
            raise CacheEngineError(f"Redis DELETE failed: {str(e)}")

    async def exists(self, key: str) -> bool:
        try:
            full_key = self._generate_key(key)
            result = await self.client.exists(full_key)
            return result > 0
        except RedisError as e:
            raise CacheEngineError(f"Redis EXISTS failed: {str(e)}")

    async def increment(self, key: str, amount: int = 1) -> int:
        try:
            full_key = self._generate_key(key)
            return await self.client.incrby(full_key, amount)
        except RedisError as e:
            raise CacheEngineError(f"Redis INCR failed: {str(e)}")

    async def check_rate_limit(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        try:
            full_key = self._generate_key(f"ratelimit:{identifier}")

            pipeline = self.client.pipeline()
            pipeline.incr(full_key)
            pipeline.ttl(full_key)

            results = await pipeline.execute()
            current_count = results[0]
            ttl = results[1]

            if current_count == 1 or ttl == -1:
                await self.client.expire(full_key, window_seconds)

            if current_count > max_requests:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {identifier}. Max: {max_requests}"
                )

            return True
        except RateLimitExceeded:
            raise
        except RedisError as e:
            return True

    async def sliding_window_rate_limit(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        try:
            full_key = self._generate_key(f"sliding:{identifier}")
            now = time.time()
            window_start = now - window_seconds

            pipeline = self.client.pipeline()
            pipeline.zremrangebyscore(full_key, 0, window_start)
            pipeline.zcard(full_key)
            pipeline.zadd(full_key, {str(now): now})
            pipeline.expire(full_key, window_seconds)

            results = await pipeline.execute()
            request_count = results[1]

            if request_count >= max_requests:
                await self.client.zrem(full_key, str(now))
                raise RateLimitExceeded(
                    f"Sliding window rate limit exceeded for {identifier}"
                )

            return True
        except RateLimitExceeded:
            raise
        except RedisError as e:
            return True

    async def acquire_lock(
        self, lock_name: str, acquire_timeout: float = 10.0, lock_timeout: float = 10.0
    ) -> str:
        identifier = str(uuid.uuid4())
        full_key = self._generate_key(f"lock:{lock_name}")
        end_time = time.time() + acquire_timeout

        while time.time() < end_time:
            try:
                if await self.client.set(
                    full_key, identifier, nx=True, px=int(lock_timeout * 1000)
                ):
                    return identifier
                await asyncio.sleep(0.05)
            except RedisError as e:
                raise DistributedLockError(
                    f"Failed to acquire lock {lock_name}: {str(e)}"
                )

        raise DistributedLockError(f"Timeout acquiring lock {lock_name}")

    async def release_lock(self, lock_name: str, identifier: str) -> bool:
        full_key = self._generate_key(f"lock:{lock_name}")

        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            result = await self.client.eval(lua_script, 1, full_key, identifier)
            return bool(result)
        except RedisError as e:
            raise DistributedLockError(f"Failed to release lock {lock_name}: {str(e)}")

    async def push_to_queue(self, queue_name: str, payload: Dict[str, Any]) -> int:
        try:
            full_key = self._generate_key(f"queue:{queue_name}")
            return await self.client.lpush(full_key, json.dumps(payload))
        except RedisError as e:
            raise CacheEngineError(f"Failed to push to queue {queue_name}: {str(e)}")

    async def pop_from_queue(
        self, queue_name: str, timeout: int = 0
    ) -> Optional[Dict[str, Any]]:
        try:
            full_key = self._generate_key(f"queue:{queue_name}")
            if timeout > 0:
                result = await self.client.brpop(full_key, timeout=timeout)
                if result:
                    return json.loads(result[1])
                return None
            else:
                result = await self.client.rpop(full_key)
                if result:
                    return json.loads(result)
                return None
        except RedisError as e:
            raise CacheEngineError(f"Failed to pop from queue {queue_name}: {str(e)}")

    async def close(self) -> None:
        await self.client.aclose()
        await self.pool.disconnect()
