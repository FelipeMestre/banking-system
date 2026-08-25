"""Kafka adapters: the write-path producer and the single status consumer (§6)."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import Any, Dict

from confluent_kafka import Consumer, KafkaError, Producer

from .config import Settings
from .kafka_config import producer_config
from .status_registry import StatusRegistry

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


class StatusConsumer:
    """One long-lived consumer on `transfer-status`, fanned out in-process.

    Runs on its own thread because the confluent-kafka client is blocking, and
    hands every verdict to the registry through the event loop.
    """

    def __init__(self, settings: Settings, registry: StatusRegistry):
        self._settings = settings
        self._registry = registry
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, _loop: asyncio.AbstractEventLoop) -> None:
        self._thread = threading.Thread(target=self._run, name="transfer-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _group_id(self) -> str:
        configured = self._settings.status_consumer_group
        return configured or f"gateway-status-{uuid.uuid4()}"

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._group_id(),
                # Replaying the topic on startup rebuilds the in-memory status
                # cache, so a restarted gateway can still answer for transfers
                # that were decided while it was down.
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

    def _dispatch(self, raw: bytes | None) -> None:
        if not raw:
            return
        try:
            self._registry.resolve_threadsafe(json.loads(raw))
        except (TypeError, ValueError):
            LOG.warning("dropping unparseable status record: %r", raw)
