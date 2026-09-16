"""Redis-backed `IStatusRegistry` (horizontal scalability).

Key/channel naming: `status:{domain}:{request_id}` (value, TTL
`ttl_seconds`), `status-events:{domain}` (Pub/Sub channel). `wait_for`
subscribes BEFORE its first cache read — that ordering, not the ~250ms poll,
is what closes the lost-wakeup race: a resolution published between a plain
GET miss and a later subscribe would otherwise never wake the waiter. The
poll is a bounded safety net for a Pub/Sub reconnect gap only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from ..interfaces.status_registry import IStatusRegistry, StatusEvent
from ..interfaces.status_registry_client import IStatusRegistryClient

LOG = logging.getLogger("openbankapi.status_registry")

_POLL_INTERVAL_SECONDS = 0.25
_DEFAULT_MAX_IN_FLIGHT = 50


class _RedisStatusRegistry:
    def __init__(
        self,
        client: IStatusRegistryClient,
        domain: str,
        ttl_seconds: int,
        max_in_flight: Optional[threading.Semaphore] = None,
    ):
        self._client = client
        self._domain = domain
        self._ttl_seconds = ttl_seconds
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending = 0
        # Bounds how many `resolve()` tasks may be scheduled onto the loop at
        # once. Without this, a Kafka consumer thread keeps calling
        # `resolve_threadsafe` at full poll speed regardless of how fast the
        # loop can drain Redis writes — under sustained load that piles up an
        # unbounded backlog of pending tasks with no thread ever slowing down
        # to match. Acquiring here blocks the *consumer* thread once the
        # limit is hit, which is the actual back-pressure signal: Kafka
        # naturally holds those messages until a slot frees up, instead of
        # the process building an ever-growing in-memory queue.
        self._in_flight = max_in_flight or threading.Semaphore(_DEFAULT_MAX_IN_FLIGHT)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def resolve_threadsafe(self, event: StatusEvent) -> None:
        """Bounded-concurrency scheduling onto the bound loop from a Kafka
        consumer thread. Still deliberately not `run_coroutine_threadsafe(...).result()`
        (design's explicit rejection) — a consumer thread must not block on
        an individual Redis round-trip. What it does do now is block on the
        `_in_flight` semaphore once too many resolves are already pending,
        so the thread naturally slows to the rate Redis can actually sustain
        instead of scheduling work faster than the loop can drain it.

        A `Task` created by `ensure_future` silently swallows a raised
        exception until something awaits it or reads `.exception()` — nothing
        here ever would, so a failed Redis write would otherwise vanish. The
        `add_done_callback` below is what makes that failure visible instead
        (and is also what releases the semaphore slot).
        """
        if self._loop is None:
            LOG.warning("status registry has no loop bound; dropping %r", event)
            return

        self._in_flight.acquire()

        def _schedule() -> None:
            task = asyncio.ensure_future(self.resolve(event))
            task.add_done_callback(self._release_and_log)

        self._loop.call_soon_threadsafe(_schedule)

    def _release_and_log(self, task: "asyncio.Task") -> None:
        self._in_flight.release()
        self._log_if_failed(task)

    @staticmethod
    def _log_if_failed(task: "asyncio.Task") -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOG.error("status registry resolve failed: %s", error, exc_info=error)

    async def resolve(self, event: StatusEvent) -> None:
        """Record a verdict and publish it. Uses `SET ... NX` so a
        redelivered verdict (at-least-once Kafka delivery) is a no-op: the
        first one written is the one a caller may already have seen, exactly
        like the in-memory predecessor's `if request_id in self._resolved: return`.
        """
        request_id = event.get("request_id")
        if not request_id:
            LOG.warning("ignoring status event without request_id: %r", event)
            return
        written = await self._client.set(
            self._status_key(request_id), json.dumps(event), ex=self._ttl_seconds, nx=True
        )
        if not written:
            return
        await self._client.publish(self._channel(), str(request_id))

    async def get(self, request_id: str) -> Optional[StatusEvent]:
        raw = await self._client.get(self._status_key(request_id))
        return json.loads(raw) if raw is not None else None

    async def wait_for(self, request_id: str, timeout: float) -> Optional[StatusEvent]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(self._channel())
        self._pending += 1
        try:
            cached = await self.get(request_id)
            if cached is not None:
                return cached

            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return None
                message = await pubsub.get_message(timeout=min(_POLL_INTERVAL_SECONDS, remaining))
                if message is not None and message.get("data") == str(request_id):
                    cached = await self.get(request_id)
                    if cached is not None:
                        return cached
                # No message (or a message for a sibling waiter's request_id)
                # still lands here roughly every `_POLL_INTERVAL_SECONDS` —
                # `get_message`'s own timeout is the reconnect safety-net
                # poll, re-checking the cache regardless of Pub/Sub activity.
        finally:
            self._pending -= 1
            await pubsub.unsubscribe(self._channel())
            await pubsub.aclose()

    def pending_count(self) -> int:
        return self._pending

    def _status_key(self, request_id: str) -> str:
        return f"status:{self._domain}:{request_id}"

    def _channel(self) -> str:
        return f"status-events:{self._domain}"


def get_redis_status_registry(
    client: IStatusRegistryClient,
    domain: str,
    ttl_seconds: int,
    max_in_flight: Optional[threading.Semaphore] = None,
) -> IStatusRegistry:
    return _RedisStatusRegistry(client, domain, ttl_seconds, max_in_flight)
