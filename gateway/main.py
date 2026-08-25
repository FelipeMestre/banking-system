"""Composition root: wires the real Kafka adapters into the FastAPI app."""
from __future__ import annotations

import logging

from .app import create_app
from .config import Settings
from .kafka_adapter import KafkaEventPublisher, StatusConsumer
from .status_registry import StatusRegistry

logging.basicConfig(level=logging.INFO)

settings = Settings.from_env()
registry = StatusRegistry(max_cached=settings.status_cache_size)
publisher = KafkaEventPublisher(settings)
consumer = StatusConsumer(settings, registry)


def _shutdown() -> None:
    consumer.stop()
    publisher.close()


app = create_app(
    settings=settings,
    publisher=publisher,
    registry=registry,
    on_start=consumer.start,
    on_stop=_shutdown,
)
