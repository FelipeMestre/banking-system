"""In-process fan-out from the single `transfer-status` consumer to waiters.

The gateway keeps exactly one long-lived Kafka consumer on `transfer-status`
(spec §6). This registry is what turns that single stream into per-request
notifications: the consumer thread hands verdicts in, and any number of
WebSocket connections or status polls read them out.
"""
from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("gateway.status")

StatusEvent = Dict[str, Any]


class StatusRegistry:
    def __init__(self, max_cached: int = 10_000):
        self._max_cached = max_cached
        self._resolved: "OrderedDict[str, StatusEvent]" = OrderedDict()
        self._waiters: Dict[str, List[asyncio.Future]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the loop the Kafka consumer thread has to hand events to."""
        self._loop = loop

    def resolve(self, event: StatusEvent) -> None:
        """Record a verdict and wake anyone waiting on it. Event-loop thread only."""
        request_id = event.get("request_id")
        if not request_id:
            LOG.warning("ignoring status event without request_id: %r", event)
            return

        # A verdict is final: at-least-once delivery means the same status can
        # arrive more than once, and the first one is the one clients already saw.
        if request_id in self._resolved:
            return

        self._resolved[request_id] = event
        while len(self._resolved) > self._max_cached:
            self._resolved.popitem(last=False)

        for waiter in self._waiters.pop(request_id, []):
            if not waiter.done():
                waiter.set_result(event)

    def resolve_threadsafe(self, event: StatusEvent) -> None:
        """Called from the Kafka consumer thread."""
        if self._loop is None:
            LOG.warning("status registry has no loop bound; dropping %r", event)
            return
        self._loop.call_soon_threadsafe(self.resolve, event)

    def get(self, request_id: str) -> Optional[StatusEvent]:
        return self._resolved.get(request_id)

    async def wait_for(self, request_id: str, timeout: float) -> Optional[StatusEvent]:
        """Wait for a verdict, or None if it does not arrive in time."""
        cached = self._resolved.get(request_id)
        if cached is not None:
            return cached

        waiter: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(request_id, []).append(waiter)

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
