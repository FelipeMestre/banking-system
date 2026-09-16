"""Shared composition root (spec §7.2 + horizontal-scalability design).

Everything both `main.py` (HTTP) and `worker.py` (Kafka consumers) need to
build their own process: settings, the DB engine/sessionmaker, the cache and
event-publisher adapters, the 6 Redis-backed `IStatusRegistry` instances, and
every writer/projection repository the consumers write through. No FastAPI
import — `worker.py` must be importable without pulling in the whole HTTP
stack, which is the entire point of the worker-http-split.
"""

from __future__ import annotations

import logging
import threading

from .config import Settings
from .infra.cache.repositories import (
    get_null_cache_repository,
    get_redis_cache_repository,
)
from .infra.cache.services.foreign_exchange_cache_service import (
    ForeignExchangeCacheService,
)
from .infra.database.config.session import create_engine, create_sessionmaker
from .infra.database.repositories import (
    PostgresAccountBalanceProjection,
    PostgresAppliedRateWriter,
    PostgresCardBalanceProjection,
    PostgresCardMovementWriter,
    PostgresDepositWriter,
    PostgresInstallmentWriter,
    PostgresTransactionWriter,
    PostgresWithdrawalWriter,
)
from .infra.foreign_exchange_service.config.foreign_exchange_config import (
    ForeignExchangeConfig,
)
from .infra.foreign_exchange_service.repository.frankfurter_repository import (
    FrankfurterRepository,
)
from .infra.kafka.repositories import KafkaEventPublisherRepository
from .infra.status_registry.repositories.redis_status_registry import (
    get_redis_status_registry,
)
from .infra.status_registry.repositories.redis_status_registry_client import (
    get_redis_status_registry_client,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("openbankapi")

settings = Settings.from_env()

engine = create_engine(settings.database_dsn)
sessionmaker = create_sessionmaker(engine)

# The balance writer is built separately and handed ONLY to `worker.py`'s
# consumers. Nothing that serves an HTTP request ever holds one (spec §3.5).
balance_projection = PostgresAccountBalanceProjection(sessionmaker)
card_balance_projection = PostgresCardBalanceProjection(sessionmaker)
# Same reasoning applies to the transactions writer: it is driven by a Kafka
# thread, not an HTTP request, so it keeps its own sessionmaker rather than
# sharing the request-scoped session `TransactionRepositoryDep` uses.
transaction_writer = PostgresTransactionWriter(sessionmaker)
# Same reasoning again, FX-19: the applied-rate audit row a converted leg
# links to is written off the same Kafka thread, not a request.
applied_rate_writer = PostgresAppliedRateWriter(sessionmaker)
deposit_writer = PostgresDepositWriter(sessionmaker)
withdrawal_writer = PostgresWithdrawalWriter(sessionmaker)
# Credit Cards Phase 2: `CardMovementConsumer` is driven by a Kafka thread
# too, same reasoning as `transaction_writer`/`applied_rate_writer` above.
card_movement_writer = PostgresCardMovementWriter(sessionmaker)
installment_writer = PostgresInstallmentWriter(sessionmaker)

cache = (
    get_redis_cache_repository(settings.redis_url)
    if settings.redis_url
    else get_null_cache_repository()
)

foreign_exchange_config = ForeignExchangeConfig()
foreign_exchange_repository = FrankfurterRepository(foreign_exchange_config)
foreign_exchange_cache_service = ForeignExchangeCacheService(
    cache, foreign_exchange_repository
)

publisher = KafkaEventPublisherRepository(settings)

# One shared Redis client backs all 6 status registries: each is a thin,
# per-domain namespace/channel view (`status:{domain}:{id}`,
# `status-events:{domain}`) over the same bounded connection pool, not 6
# separate pools — see design's "Redis connection sizing" decision.
_status_registry_client = get_redis_status_registry_client(
    settings.redis_url, settings.redis_pool_size
)
# Shared across all 6 registries for the same reason as the client above:
# they draw from one connection pool, so the cap on concurrent in-flight
# `resolve()` tasks has to be shared too — 6 independent per-domain limits
# of `redis_pool_size` each would still let 6x the pool's actual capacity
# pile up at once and reproduce the exhaustion this is meant to prevent.
_status_resolve_semaphore = threading.Semaphore(settings.redis_pool_size)
status_registry = get_redis_status_registry(
    _status_registry_client, "transfer", settings.status_ttl_seconds, _status_resolve_semaphore
)
purchase_status_registry = get_redis_status_registry(
    _status_registry_client, "purchase", settings.status_ttl_seconds, _status_resolve_semaphore
)
card_payment_status_registry = get_redis_status_registry(
    _status_registry_client,
    "card_payment",
    settings.status_ttl_seconds,
    _status_resolve_semaphore,
)
card_payment_settlement_registry = get_redis_status_registry(
    _status_registry_client,
    "card_payment_settlement",
    settings.status_ttl_seconds,
    _status_resolve_semaphore,
)
deposit_status_registry = get_redis_status_registry(
    _status_registry_client, "deposit", settings.status_ttl_seconds, _status_resolve_semaphore
)
withdrawal_status_registry = get_redis_status_registry(
    _status_registry_client,
    "withdrawal",
    settings.status_ttl_seconds,
    _status_resolve_semaphore,
)

ALL_STATUS_REGISTRIES = (
    status_registry,
    purchase_status_registry,
    card_payment_status_registry,
    card_payment_settlement_registry,
    deposit_status_registry,
    withdrawal_status_registry,
)


async def close_status_registry_client() -> None:
    await _status_registry_client.close()
