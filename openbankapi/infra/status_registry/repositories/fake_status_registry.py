"""In-memory `IStatusRegistry` test double (horizontal scalability).

Used by `Harness.build()` (`tests/conftest.py`) to keep the default test
suite infra-free. Parity with the real Redis-backed registry is proven by
the shared contract tests in `tests/unit/status_registry/`, minus the real
subscribe-before-check race itself: a fake's ordering is trivially correct
by construction, so only a real-Redis test
(`tests/integration/test_redis_status_registry.py`) can exercise that.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, List, Optional

from ..interfaces.status_registry import StatusEvent


class FakeStatusRegistry:
    def __init__(self, *, on_subscribed: Optional[Callable[[], Awaitable[None]]] = None):
        # Test-only synchronization point: a race test awaits this between
        # "subscribe" (the waiter future is registered) and "check cache" —
        # the exact window the real registry's subscribe-before-check
        # ordering closes — to deterministically land a concurrent `resolve`
        # inside it without relying on real network timing.
        self._on_subscribed = on_subscribed
        self._resolved: Dict[str, StatusEvent] = {}
        self._waiters: Dict[str, List[asyncio.Future]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def resolve_threadsafe(self, event: StatusEvent) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.resolve(event)))

    async def resolve(self, event: StatusEvent) -> None:
        request_id = event.get("request_id")
        if not request_id:
            return
        # A verdict is final: at-least-once delivery means the same status
        # can arrive more than once, and the first one is the one already seen.
        if request_id in self._resolved:
            return
        self._resolved[request_id] = event
        for waiter in self._waiters.pop(request_id, []):
            if not waiter.done():
                waiter.set_result(event)

    async def get(self, request_id: str) -> Optional[StatusEvent]:
        return self._resolved.get(request_id)

    async def wait_for(self, request_id: str, timeout: float) -> Optional[StatusEvent]:
        cached = self._resolved.get(request_id)
        if cached is not None:
            return cached

        waiter: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(request_id, []).append(waiter)

        if self._on_subscribed is not None:
            await self._on_subscribed()

        # A resolve landing exactly during `_on_subscribed` already woke the
        # future above (or, with no hook, this re-check is simply a no-op
        # fast path). Either way, mirrors the real registry's "subscribe,
        # then check the cache" order.
        cached = self._resolved.get(request_id)
        if cached is not None:
            self._discard(request_id, waiter)
            return cached

        try:
            return await asyncio.wait_for(waiter, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._discard(request_id, waiter)

    def pending_count(self) -> int:
        return sum(len(waiters) for waiters in self._waiters.values())

    def _discard(self, request_id: str, waiter: asyncio.Future) -> None:
        waiters = self._waiters.get(request_id)
        if not waiters:
            return
        if waiter in waiters:
            waiters.remove(waiter)
        if not waiters:
            self._waiters.pop(request_id, None)


def get_fake_status_registry(
    *, on_subscribed: Optional[Callable[[], Awaitable[None]]] = None
) -> FakeStatusRegistry:
    return FakeStatusRegistry(on_subscribed=on_subscribed)
