"""Composition root (spec §7.2).

The only module allowed to know about every concrete adapter and wire them
together. Nothing else imports Redis, asyncpg or confluent-kafka directly.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi_plugin.fast_api_client import Auth0FastAPI

from .app import create_app
from .config import Settings
from .infra.cache.repositories import get_null_cache_repository, get_redis_cache_repository
from .infra.cache.services.foreign_exchange_cache_service import ForeignExchangeCacheService
from .infra.database.repositories import PostgresAccountBalanceProjection
from .infra.database.config.session import create_engine, create_sessionmaker
from .infra.foreign_exchange_service.config.foreign_exchange_config import ForeignExchangeConfig
from .infra.foreign_exchange_service.repository.frankfurter_repository import FrankfurterRepository
from .infra.kafka.consumers import AccountBalanceConsumer, TransferStatusConsumer
from .infra.kafka.repositories import KafkaEventPublisherRepository
from .infra.kafka.status_registry import StatusRegistry

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("openbankapi")

settings = Settings.from_env()

engine = create_engine(settings.database_dsn)
sessionmaker = create_sessionmaker(engine)

# The balance writer is built separately and handed ONLY to the consumer below.
# Nothing that serves an HTTP request ever holds one (spec §3.5). Every other
balance_projection = PostgresAccountBalanceProjection(sessionmaker)

cache = get_redis_cache_repository(settings.redis_url) if settings.redis_url else get_null_cache_repository()

foreign_exchange_config = ForeignExchangeConfig()
foreign_exchange_repository = FrankfurterRepository(foreign_exchange_config)
foreign_exchange_cache_service = ForeignExchangeCacheService(cache, foreign_exchange_repository)

publisher = KafkaEventPublisherRepository(settings)
status_registry = StatusRegistry(max_cached=settings.status_cache_size)
status_consumer = TransferStatusConsumer(settings, status_registry)
balance_consumer = AccountBalanceConsumer(settings, balance_projection, cache)

# None until AUTH0_DOMAIN/AUTH0_AUDIENCE are set (an Auth0 "API" resource has
# to exist first — see config/dependencies.py for how routes degrade to a
# clear 503 instead of crashing the whole app when this is unset).
auth0 = (
    Auth0FastAPI(domain=settings.auth0_domain, audience=settings.auth0_audience)
    if settings.auth0_domain and settings.auth0_audience
    else None
)


def _start(loop: asyncio.AbstractEventLoop) -> None:
    status_consumer.start(loop)
    balance_consumer.start(loop)


def _stop() -> None:
    status_consumer.stop()
    balance_consumer.stop()
    publisher.close()


async def _stop_async() -> None:
    await cache.close()
    await engine.dispose()


app = create_app(
    settings=settings,
    cache=cache,
    publisher=publisher,
    sessionmaker=sessionmaker,
    status_registry=status_registry,
    auth0=auth0,
    on_start=_start,
    on_stop=_stop,
    on_stop_async=_stop_async,
    foreign_exchange_cache_service=foreign_exchange_cache_service,
)
