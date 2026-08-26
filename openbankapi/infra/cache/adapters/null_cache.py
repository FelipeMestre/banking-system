"""A cache that caches nothing.

Used by the test suite and by any local run without Redis. Because the rest of
the system treats a miss as normal, this is a complete implementation, not a
stub — the API behaves identically, just without the cache.
"""
from __future__ import annotations

from typing import Any, Optional

from ..interfaces.cache_service import DEFAULT_TTL_SECONDS


class NullCache:
    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None
