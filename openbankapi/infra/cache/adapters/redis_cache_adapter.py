"""Redis implementation of ICacheService.

A cache that can take the API down is not a cache, it is a second database with
worse durability. Every operation here swallows connection errors and degrades
to a miss: a Redis outage makes reads slower, never failed. That is the whole
reason the port exists rather than calling redis directly from a controller.

Values are JSON. Storing pickles would couple the cache's contents to this
process's class definitions, and a deploy would then have to invalidate
everything.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from ..interfaces.cache_service import DEFAULT_TTL_SECONDS

LOG = logging.getLogger("openbankapi.cache")


class RedisCacheAdapter:
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
