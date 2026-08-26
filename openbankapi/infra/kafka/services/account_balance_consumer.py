"""Keeps `accounts.balance` in sync with the ledger (spec §3.6).

This is the ONE component allowed to write `balance`, and it holds an
`IAccountBalanceProjection` rather than a full repository so that stays true by
construction.

Two things differ deliberately from the transfer-status consumer:

- **A stable, shared group id.** Status delivery needs every instance to see
  every partition; this does not. Two instances writing the same projection
  would just do redundant work, so the partitions are split like an ordinary
  consumer group.
- **The write is awaited.** The thread blocks on each database update rather
  than firing it off. That is what gives the consumer backpressure: without it,
  a burst of balance records becomes an unbounded queue of pending writes that
  nothing is allowed to drop.

Replay is safe. `account-balances` is compacted and a record is a snapshot, so
re-applying the newest value per key converges on the same state — which is why
offsets are not committed at all.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ....domain.events import BalanceUpdated
from ...cache.interfaces.cache_service import cache_key
from ...database.interfaces import IAccountBalanceProjection

LOG = logging.getLogger("openbankapi.kafka.balances")

# How long the consumer thread waits for one database write before giving up on
# it. Long enough to ride out a slow query, short enough that a wedged pool
# does not freeze the consumer forever.
_WRITE_TIMEOUT_SECONDS = 30


class AccountBalanceConsumer:
    def __init__(
        self,
        settings: Settings,
        projection: IAccountBalanceProjection,
        cache,
    ):
        self._settings = settings
        self._projection = projection
        self._cache = cache
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        # The consumer runs on a thread but the projection is async, so it needs
        # the API's loop to hand coroutines back to.
        self._loop = loop
        self._thread = threading.Thread(target=self._run, name="account-balances", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._settings.balance_consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.account_balances_topic])
        LOG.info("consuming %s", self._settings.account_balances_topic)
        try:
            while not self._stopping.is_set():
                message = consumer.poll(0.5)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() != KafkaError._PARTITION_EOF:
                        LOG.error("consumer error: %s", message.error())
                    continue
                self._handle(message.value())
        finally:
            consumer.close()

    def _handle(self, raw) -> None:
        event = self._parse(raw)
        if event is None:
            return
        if self._loop is None:
            LOG.warning("no loop bound; dropping balance for %s", event.account_id)
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._apply(event), self._loop)
            future.result(timeout=_WRITE_TIMEOUT_SECONDS)
        except Exception as error:  # noqa: BLE001 - one bad row must not kill the consumer
            LOG.error("failed to project balance for %s: %s", event.account_id, error)

    @staticmethod
    def _parse(raw) -> Optional[BalanceUpdated]:
        if not raw:
            return None
        try:
            return BalanceUpdated.from_payload(json.loads(raw))
        except (TypeError, ValueError, KeyError) as error:
            LOG.warning("dropping malformed balance record: %s", error)
            return None

    async def _apply(self, event: BalanceUpdated) -> None:
        updated = await self._projection.apply_balance(event.account_id, event.balance)
        if not updated:
            # The ledger runs accounts reference data has never heard of. Not an
            # error: there is simply no row to project onto yet.
            LOG.info("no account row for %s; skipping projection", event.account_id)
            return
        # Invalidate after the write, never before: invalidating first leaves a
        # window where a concurrent read repopulates the cache with the old value.
        await self._cache.delete(cache_key("account", event.account_id))
