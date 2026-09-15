"""Fake `IStatusRegistryClient` double for `_RedisStatusRegistry` unit tests.

Simulates just enough of Redis's GET/SET/PUBLISH/Pub-Sub contract to drive
`_RedisStatusRegistry` without a real Redis: a dict for values, and one
`asyncio.Queue` per active subscription so a publish reaches every
already-subscribed pubsub handle. The actual subscribe-before-check RACE
against real Redis timing is only provable against real Redis — see
`tests/integration/test_redis_status_registry.py` — this double exists to
unit-test the registry's own logic (TTL, ordering of calls, scheduling),
not to reproduce Redis's network timing.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple


class _FakePubSub:
    def __init__(self, client: "FakeRedisStatusRegistryClient"):
        self._client = client
        self._channel: Optional[str] = None
        self._queue: "asyncio.Queue[dict]" = asyncio.Queue()

    async def subscribe(self, channel: str) -> None:
        self._channel = channel
        self._client._subscribers.setdefault(channel, []).append(self._queue)

    async def unsubscribe(self, channel: str) -> None:
        subscribers = self._client._subscribers.get(channel, [])
        if self._queue in subscribers:
            subscribers.remove(self._queue)

    async def get_message(self, *, timeout: float) -> Optional[dict]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def aclose(self) -> None:
        return None


class FakeRedisStatusRegistryClient:
    def __init__(self):
        self._store: Dict[str, str] = {}
        self.set_calls: List[Tuple[str, str, int, bool]] = []
        self._subscribers: Dict[str, List["asyncio.Queue[dict]"]] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        self.set_calls.append((key, value, ex, nx))
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def publish(self, channel: str, message: str) -> None:
        for queue in self._subscribers.get(channel, []):
            await queue.put({"type": "message", "data": message})

    def pubsub(self):
        return _FakePubSub(self)

    async def close(self) -> None:
        return None
