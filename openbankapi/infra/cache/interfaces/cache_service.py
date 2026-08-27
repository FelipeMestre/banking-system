"""The cache port (spec §8.2, cache-aside).

Routers and services depend on `ICacheService`, never on a concrete adapter —
same split as `infra/database/interfaces`.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol

# Spec §8.2: `{entity}:{id}`, e.g. account:1234567890123456, customer:{uuid}.
DEFAULT_TTL_SECONDS = 300


def cache_key(entity: str, identifier: Any) -> str:
    return f"{entity}:{identifier}"


class ICacheService(Protocol):
    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value, or None on a miss OR on any cache failure."""
        ...

    async def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def close(self) -> None: ...
