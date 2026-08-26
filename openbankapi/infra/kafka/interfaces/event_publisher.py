"""The outbound Kafka port."""
from __future__ import annotations

from typing import Any, Dict, Protocol


class IEventPublisher(Protocol):
    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        """Publish `value` as JSON under `key`.

        Synchronous on purpose, and it must NOT block on delivery. `POST
        /transfer` answers immediately (spec §8.1); making this async would put
        an await — and a scheduler hop — on the one path that must not have one,
        for a call that does not wait on I/O anyway.
        """
        ...
