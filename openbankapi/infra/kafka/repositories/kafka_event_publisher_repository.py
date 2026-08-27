"""confluent-kafka producer implementing IEventPublisher.

Ported unchanged from the v1 gateway, including the fire-and-forget semantics:
`POST /transfer` must answer without waiting for an ack (spec §8.1), so failures
surface through the delivery callback rather than the HTTP response.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from confluent_kafka import Producer

from ....config import Settings
from ..config.kafka_config import producer_config

LOG = logging.getLogger("openbankapi.kafka")


class KafkaEventPublisherRepository:
    def __init__(self, settings: Settings):
        self._producer = Producer(producer_config(settings, client_id="openbankapi-producer"))

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
