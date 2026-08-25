"""Composition root: wires the real Kafka adapter into the FastAPI app."""
from __future__ import annotations

import logging

from .app import create_app
from .config import Settings
from .kafka_adapter import KafkaEventPublisher

logging.basicConfig(level=logging.INFO)

settings = Settings.from_env()
publisher = KafkaEventPublisher(settings)

app = create_app(settings=settings, publisher=publisher, on_stop=publisher.close)
