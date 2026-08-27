"""The cache-aside helper every ABM read goes through (spec §8.2).

Single-resource reads only. List endpoints are deliberately not cached: their
key space is unbounded (every limit/offset combination) and no write can
reliably invalidate them, so a cached list is a stale list with no expiry story.

A 404 is not cached either — caching absence means a resource created a moment
later stays invisible for the whole TTL.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional


async def read_through(
    cache,
    key: str,
    load: Callable[[], Awaitable[Optional[Any]]],
    to_cacheable: Callable[[Any], Any],
    ttl_seconds: int,
) -> Optional[Any]:
    cached = await cache.get(key)
    if cached is not None:
        return cached
    loaded = await load()
    if loaded is None:
        return None
    payload = to_cacheable(loaded)
    await cache.set(key, payload, ttl_seconds)
    return payload
