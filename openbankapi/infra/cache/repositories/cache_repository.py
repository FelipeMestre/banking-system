"""Concrete `ICacheService` adapters.

Both classes are private: nothing outside this module names `_RedisCacheRepository`
or `_NullCacheRepository` directly. Callers get one through `get_redis_cache_repository`
/ `get_null_cache_repository`, and depend on `ICacheService` (`infra/cache/interfaces`)
after that — the same interface/repository split as `infra/database`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from ..interfaces.cache_service import DEFAULT_TTL_SECONDS, ICacheService

LOG = logging.getLogger("openbankapi.cache")


class _RedisCacheRepository:
    """A cache that can take the API down is not a cache, it is a second database
    with worse durability. Every operation here swallows connection errors and
    degrades to a miss: a Redis outage makes reads slower, never failed.

    Values are JSON. Storing pickles would couple the cache's contents to this
    process's class definitions, and a deploy would then have to invalidate
    everything.
    """

    def __init__(self, url: str):
        self._client = aioredis.from_url(url, encoding="utf-8", decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        try:
            raw = await self._client.get(key)
        except RedisError as error:
            LOG.warning("cache unavailable on get(%s): %s", key, error)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            # A poisoned entry must not break the read path; drop it and miss.
            LOG.warning("discarding unparseable cache entry: %s", key)
            await self.delete(key)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        try:
            await self._client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except RedisError as error:
            LOG.warning("cache unavailable on set(%s): %s", key, error)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except RedisError as error:
            # The dangerous one: a failed invalidation leaves a stale entry that
            # will be served until its TTL expires. Logged at warning so it is
            # visible, but still not worth failing the write the caller made.
            LOG.warning("cache invalidation failed for %s: %s", key, error)

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except (RedisError, AttributeError):
            pass


class _NullCacheRepository:
    """A cache that caches nothing.

    Used for any local run without Redis. Because the rest of the system
    treats a miss as normal, this is a complete implementation, not a stub —
    the API behaves identically, just without the cache.
    """

    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


def get_redis_cache_repository(url: str) -> ICacheService:
    return _RedisCacheRepository(url)


def get_null_cache_repository() -> ICacheService:
    return _NullCacheRepository()
