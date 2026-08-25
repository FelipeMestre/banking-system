"""Kafka adapter for the write path (spec §6)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from confluent_kafka import Producer

from .config import Settings
from .kafka_config import producer_config

LOG = logging.getLogger("gateway.kafka")


class KafkaEventPublisher:
    """Fire-and-forget producer.

    `POST /transfer` must answer immediately (§6), so this never blocks on an
    ack. Failures surface through the delivery callback, not the HTTP response.
    """

    def __init__(self, settings: Settings):
        self._producer = Producer(producer_config(settings, client_id="gateway-producer"))

    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        self._producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            on_delivery=self._on_delivery,
        )
        # Serves delivery callbacks without waiting for this record's ack.
        self._producer.poll(0)

    def close(self) -> None:
        self._producer.flush(10)

    @staticmethod
    def _on_delivery(err, msg) -> None:
        if err is not None:
            LOG.error("failed to deliver to %s: %s", msg.topic() if msg else "?", err)
