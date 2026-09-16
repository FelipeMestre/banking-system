"""Concrete Redis client for the status registry (private class + factory).

Owns its own `redis.asyncio` connection pool, separate from `infra/cache`'s:
`wait_for` needs a dedicated Pub/Sub connection per waiter plus a
value get/set connection — a different traffic shape from the cache-aside
port's simple get/set/delete. `BlockingConnectionPool` fails fast (raises
after its `timeout`) instead of silently queueing forever once
`REDIS_POOL_SIZE` connections are all checked out.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from ..interfaces.status_registry_client import IStatusRegistryClient


class _RedisStatusRegistryClient:
    def __init__(self, url: str, pool_size: int):
        pool = aioredis.BlockingConnectionPool.from_url(
            url, max_connections=pool_size, decode_responses=True
        )
        self._client = aioredis.Redis(connection_pool=pool)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        written = await self._client.set(key, value, ex=ex, nx=nx)
        # Plain `SET` (no `nx`) always returns truthy on success; `SET NX`
        # returns `None` when the key already existed.
        return bool(written)

    async def publish(self, channel: str, message: str) -> None:
        await self._client.publish(channel, message)

    def pubsub(self):
        # `ignore_subscribe_messages=True`: `get_message` then only ever
        # returns real data messages, never the subscribe/unsubscribe
        # confirmation Redis sends first — `_RedisStatusRegistry.wait_for`
        # would otherwise have to filter those out itself.
        return self._client.pubsub(ignore_subscribe_messages=True)

    async def close(self) -> None:
        await self._client.aclose()


def get_redis_status_registry_client(url: str, pool_size: int) -> IStatusRegistryClient:
    return _RedisStatusRegistryClient(url, pool_size)
