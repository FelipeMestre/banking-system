"""Composition root (spec §7.2).

The only module allowed to know about every concrete adapter and wire them
together. Nothing else imports Redis, asyncpg or confluent-kafka directly.
"""
from __future__ import annotations

import asyncio
import logging

from .app import create_app
from .config import Settings
from .domain.service import AccountService, TransferService
from .infra.cache.adapters.null_cache import NullCache
from .infra.cache.adapters.redis_cache_adapter import RedisCacheAdapter
from .infra.database.repositories import (
    PostgresCustomerRepository,
    PostgresAccountBalanceProjection,
    PostgresAccountRepository,
    PostgresLocationRepository,
    PostgresBranchRepository,
)
from .infra.database.session import create_engine, create_sessionmaker
from .infra.kafka.adapters import KafkaEventPublisher
from .infra.kafka.services import AccountBalanceConsumer, StatusConsumer, StatusRegistry

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("openbankapi")

settings = Settings.from_env()

engine = create_engine(settings.database_dsn)
sessionmaker = create_sessionmaker(engine)

location_repository = PostgresLocationRepository(sessionmaker)
branch_repository = PostgresBranchRepository(sessionmaker)
customer_repository = PostgresCustomerRepository(sessionmaker)
account_repository = PostgresAccountRepository(sessionmaker)

# The balance writer is built separately and handed ONLY to the consumer below.
# Nothing that serves an HTTP request ever holds one (spec §3.5).
balance_projection = PostgresAccountBalanceProjection(sessionmaker)

cache = RedisCacheAdapter(settings.redis_url) if settings.redis_url else NullCache()

publisher = KafkaEventPublisher(settings)
status_registry = StatusRegistry(max_cached=settings.status_cache_size)
status_consumer = StatusConsumer(settings, status_registry)
balance_consumer = AccountBalanceConsumer(settings, balance_projection, cache)

transfer_service = TransferService(settings, publisher)
account_service = AccountService(settings, account_repository, publisher)


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
    transfer_service=transfer_service,
    account_service=account_service,
    status_registry=status_registry,
    location_repository=location_repository,
    branch_repository=branch_repository,
    customer_repository=customer_repository,
    account_repository=account_repository,
    cache=cache,
    on_start=_start,
    on_stop=_stop,
    on_stop_async=_stop_async,
)
