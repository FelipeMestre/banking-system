"""Outbound ports. Keeps the HTTP layer independent of the Kafka client."""
from __future__ import annotations

from typing import Any, Dict, Protocol


class EventPublisher(Protocol):
    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        """Publish `value` as JSON under `key`. Must not block on delivery."""
        ...
