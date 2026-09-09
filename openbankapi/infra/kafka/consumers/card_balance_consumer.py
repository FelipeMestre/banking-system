"""Keeps `card_accounts.used_credit` in sync with the card ledger (card-balances).

Mirrors `AccountBalanceConsumer` exactly: the only writer of `used_credit`,
holds an `ICardBalanceProjection` rather than a full repository so that stays
true by construction. Replay is safe: `card-balances` is compacted and a
record is a snapshot, so re-applying the newest value per key converges.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ....domain.events.card_balance_updated import CardBalanceUpdated
from ...cache.interfaces.cache_service import cache_key
from ...database.interfaces import ICardBalanceProjection

LOG = logging.getLogger("openbankapi.kafka.card_balances")

_WRITE_TIMEOUT_SECONDS = 30


class CardBalanceConsumer:
    def __init__(
        self,
        settings: Settings,
        projection: ICardBalanceProjection,
        cache,
    ):
        self._settings = settings
        self._projection = projection
        self._cache = cache
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread = threading.Thread(target=self._run, name="card-balances", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._settings.card_balance_consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.card_balances_topic])
        LOG.info("consuming %s", self._settings.card_balances_topic)
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
            LOG.warning("no loop bound; dropping balance for %s", event.card_account_id)
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._apply(event), self._loop)
            future.result(timeout=_WRITE_TIMEOUT_SECONDS)
        except Exception as error:  # noqa: BLE001
            LOG.error("failed to project card balance for %s: %s", event.card_account_id, error)

    @staticmethod
    def _parse(raw) -> Optional[CardBalanceUpdated]:
        if not raw:
            return None
        try:
            return CardBalanceUpdated.from_payload(json.loads(raw))
        except (TypeError, ValueError, KeyError) as error:
            LOG.warning("dropping malformed card balance record: %s", error)
            return None

    async def _apply(self, event: CardBalanceUpdated) -> bool:
        try:
            card_account_id = uuid.UUID(event.card_account_id)
        except ValueError as error:
            LOG.warning("dropping malformed card_account_id %s: %s", event.card_account_id, error)
            return False
        updated = await self._projection.apply_used_credit(card_account_id, event.used_credit)
        if not updated:
            LOG.info("no card_account row for %s; skipping projection", event.card_account_id)
            return False
        await self._cache.delete(cache_key("card_account", event.card_account_id))
        return True
