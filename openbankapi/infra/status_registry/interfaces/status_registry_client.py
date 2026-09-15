"""Thin Redis client port for the status registry's key-value + Pub/Sub needs.

Deliberately separate from `ICacheService` (`infra/cache`): that port is a
narrow cache-aside contract (get/set/delete/close) consumed by FX code, and
adding Pub/Sub there would force every `ICacheService` implementer
(including `_NullCacheRepository`) to fake a channel subscription it never
needs. A second, smaller port is cheaper than widening a shared one.
"""
from __future__ import annotations

from typing import Optional, Protocol


class IStatusRegistryPubSub(Protocol):
    async def subscribe(self, channel: str) -> None: ...

    async def unsubscribe(self, channel: str) -> None: ...

    async def get_message(self, *, timeout: float) -> Optional[dict]:
        """Return the next data message on the subscribed channel(s), or
        None if none arrives within `timeout`. Subscribe-confirmation
        messages are never returned here (see `_RedisStatusRegistryClient`'s
        `ignore_subscribe_messages=True`)."""
        ...

    async def aclose(self) -> None: ...


class IStatusRegistryClient(Protocol):
    async def get(self, key: str) -> Optional[str]: ...

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        """Set `key`. With `nx=True`, only writes if `key` does not already
        exist (Redis `SET ... NX`), returning whether the write happened —
        this is what makes a redelivered verdict a no-op instead of a
        silent overwrite of the one a caller may already have seen."""
        ...

    async def publish(self, channel: str, message: str) -> None: ...

    def pubsub(self) -> IStatusRegistryPubSub: ...

    async def close(self) -> None: ...
