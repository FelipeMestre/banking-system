"""The single long-lived consumer on `transfer-status` (spec §8.1).

Ported from the v1 gateway. One consumer per process fans out in-process to
every waiting WebSocket, rather than one consumer per connection.
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

LOG = logging.getLogger("openbankapi.kafka.status")


class TransferStatusConsumer:
    def __init__(self, settings: Settings, registry: IStatusRegistry):
        self._settings = settings
        self._registry = registry
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, _loop: asyncio.AbstractEventLoop) -> None:
        self._thread = threading.Thread(target=self._run, name="transfer-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _group_id(self) -> str:
        # Fixed, shared across every worker instance: the status registry is
        # Redis-backed now (horizontal scalability), so any instance that
        # sees the resolving event can make it visible to every replica —
        # a shared group.id lets Kafka split partitions across instances
        # instead of handing each one a full duplicate copy of the topic.
        return self._settings.status_consumer_group

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._group_id(),
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.transfer_status_topic])
        LOG.info("consuming %s", self._settings.transfer_status_topic)
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
