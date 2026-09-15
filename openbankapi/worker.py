"""Kafka-consumer-only process (worker-http-split — horizontal scalability).

Mirrors `batch/run_once.py`'s no-FastAPI-import discipline: imports
`composition.py` (shared engine/registries/writers) plus the 9 consumers,
never `app.py`/`create_app`/FastAPI. Runs its own asyncio loop, binds every
status registry to it, starts all 9 consumers, and blocks until
SIGTERM/SIGINT, draining consumers (stopping their poll threads and joining
them) before disposing the engine/Redis client/cache/publisher.

Real entry point: `python -m openbankapi.worker`.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from . import composition
from .infra.kafka.consumers import (
    AccountBalanceConsumer,
    CardBalanceConsumer,
    CardMovementConsumer,
    CardPaymentStatusConsumer,
    DepositStatusConsumer,
    PurchaseStatusConsumer,
    TransactionConsumer,
    TransferStatusConsumer,
    WithdrawalStatusConsumer,
)

LOG = logging.getLogger("openbankapi.worker")


def _build_consumers() -> list:
    return [
        TransferStatusConsumer(composition.settings, composition.status_registry),
        PurchaseStatusConsumer(composition.settings, composition.purchase_status_registry),
        CardPaymentStatusConsumer(composition.settings, composition.card_payment_status_registry),
        DepositStatusConsumer(composition.settings, composition.deposit_status_registry),
        WithdrawalStatusConsumer(composition.settings, composition.withdrawal_status_registry),
        AccountBalanceConsumer(composition.settings, composition.balance_projection, composition.cache),
        CardBalanceConsumer(composition.settings, composition.card_balance_projection, composition.cache),
        TransactionConsumer(
            composition.settings,
            composition.transaction_writer,
            composition.applied_rate_writer,
            composition.deposit_writer,
            composition.withdrawal_writer,
        ),
        CardMovementConsumer(
            composition.settings,
            composition.card_movement_writer,
            composition.installment_writer,
            composition.applied_rate_writer,
            settlement_registry=composition.card_payment_settlement_registry,
        ),
    ]


async def _run() -> None:
    loop = asyncio.get_running_loop()
    for registry in composition.ALL_STATUS_REGISTRIES:
        registry.bind_loop(loop)

    consumers = _build_consumers()
    for consumer in consumers:
        consumer.start(loop)
    LOG.info("openbankapi-worker started: %d consumers running", len(consumers))

    shutdown = asyncio.Event()

    def _request_shutdown() -> None:
        LOG.info("shutdown signal received")
        shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown)

    await shutdown.wait()

    LOG.info("draining consumers")
    for consumer in consumers:
        consumer.stop()
    composition.publisher.close()
    await composition.cache.close()
    await composition.close_status_registry_client()
    await composition.engine.dispose()
    LOG.info("openbankapi-worker stopped")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
