"""Port for per-domain async-status resolution (horizontal scalability).

Same call surface `openbankapi.infra.kafka.status_registry.StatusRegistry`
(the in-memory predecessor this replaces) already exposed, kept in lockstep
so every existing caller needs no change beyond the type hint plus an
`await` on the two methods a Redis-backed implementation must do I/O for
(`get`, `resolve`). `resolve_threadsafe`, `bind_loop` and `pending_count`
keep their exact prior signatures — they are the cross-thread/introspection
surface, never awaited by a caller.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Protocol

StatusEvent = Dict[str, Any]


class IStatusRegistry(Protocol):
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the loop a Kafka consumer thread has to hand events to."""
        ...

    def resolve_threadsafe(self, event: StatusEvent) -> None:
        """Called from a Kafka consumer thread. Never blocks the caller
        thread on the Redis round-trip `resolve` performs."""
        ...

    async def resolve(self, event: StatusEvent) -> None:
        """Record a verdict and wake anyone waiting on it."""
        ...

    async def get(self, request_id: str) -> Optional[StatusEvent]:
        ...

    async def wait_for(self, request_id: str, timeout: float) -> Optional[StatusEvent]:
        """Wait for a verdict, or None if it does not arrive in time."""
        ...

    def pending_count(self) -> int:
        ...
