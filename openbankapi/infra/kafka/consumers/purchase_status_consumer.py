"""The single long-lived consumer on `purchase-status` (Credit Cards Phase 2).

Mirrors `TransferStatusConsumer` exactly: one consumer per process fans out
in-process to every waiting WebSocket/poll, rather than one consumer per
connection. Uses its own `StatusRegistry` instance (never the transfer one) —
`request_id` is only unique within its own domain's Kafka topic, and a card
purchase and a transfer could coincidentally share one.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ..status_registry import StatusRegistry

LOG = logging.getLogger("openbankapi.kafka.purchase_status")


class PurchaseStatusConsumer:
    def __init__(self, settings: Settings, registry: StatusRegistry):
        self._settings = settings
        self._registry = registry
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, _loop: asyncio.AbstractEventLoop) -> None:
        self._thread = threading.Thread(target=self._run, name="purchase-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _group_id(self) -> str:
        # Unique per process: every instance must see every partition, or a
        # socket waiting here would never learn a verdict delivered elsewhere.
        configured = self._settings.purchase_status_consumer_group
        return configured or f"openbankapi-purchase-status-{uuid.uuid4()}"

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._group_id(),
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.purchase_status_topic])
        LOG.info("consuming %s", self._settings.purchase_status_topic)
        try:
            while not self._stopping.is_set():
                message = consumer.poll(0.5)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() != KafkaError._PARTITION_EOF:
                        LOG.error("consumer error: %s", message.error())
                    continue
                self._dispatch(message.value())
        finally:
            consumer.close()

    def _dispatch(self, raw) -> None:
        if not raw:
            return
        try:
            self._registry.resolve_threadsafe(json.loads(raw))
        except (TypeError, ValueError):
            LOG.warning("dropping unparseable status record")
