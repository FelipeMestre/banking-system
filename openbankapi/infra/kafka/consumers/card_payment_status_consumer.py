"""The single long-lived consumer on `card-payment-status` (Credit Cards
Phase 3). Mirrors `PurchaseStatusConsumer` exactly: one consumer per process
fans out in-process to every waiting WebSocket/poll. Uses its OWN
`IStatusRegistry` instance (never `transfer`'s or `purchase`'s) — `request_id`
is only unique within its own domain's Kafka topic, and a card payment and a
purchase (or a transfer) could coincidentally share one.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ...status_registry.interfaces.status_registry import IStatusRegistry

LOG = logging.getLogger("openbankapi.kafka.card_payment_status")


class CardPaymentStatusConsumer:
    def __init__(self, settings: Settings, registry: IStatusRegistry):
        self._settings = settings
        self._registry = registry
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, _loop: asyncio.AbstractEventLoop) -> None:
        self._thread = threading.Thread(target=self._run, name="card-payment-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _group_id(self) -> str:
        # Fixed, shared across every worker instance — see transfer_status_consumer.py.
        return self._settings.card_payment_status_consumer_group

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._group_id(),
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        consumer.subscribe([self._settings.card_payment_status_topic])
        LOG.info("consuming %s", self._settings.card_payment_status_topic)
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
