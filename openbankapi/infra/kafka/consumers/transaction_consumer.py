"""Populates the `transactions` read model off `account-events` (spec §3.1).

Same thread/loop/`run_coroutine_threadsafe` shape as
`account_balance_consumer.py`, and the same reasoning for a shared, stable
consumer group: this writes a shared Postgres table, not a process-local
fan-out, so splitting partitions across instances is the right thing to do.

`transfer_requested` is deliberately never dispatched: it is not yet a
resolved outcome (spec §3.1). `insert` on `ITransactionRepository` is
idempotent by construction (`ON CONFLICT DO NOTHING`), so at-least-once
redelivery here never needs its own dedup check.

FX-19: an `incoming_payment` event that carries a `conversion` dict (attached
by `account-service/domain.py`'s `_incoming` when the transfer needed a
currency conversion) is persisted to `applied_rates` first, and the returned
id threaded into the transaction row as `applied_rate_id`. `outgoing_payment`
and `declined_payment` never carry `conversion` and always link `None`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ...database.interfaces.applied_rate_repository import IAppliedRateRepository
from ...database.interfaces.transaction_repository import ITransactionRepository

LOG = logging.getLogger("openbankapi.kafka.transactions")

_WRITE_TIMEOUT_SECONDS = 30

_EVENT_TO_ROW_TYPE = {
    "outgoing_payment": "debit",
    "incoming_payment": "credit",
    "declined_payment": "declined",
}


class TransactionConsumer:
    def __init__(
        self,
        settings: Settings,
        repository: ITransactionRepository,
        applied_rate_repository: Optional[IAppliedRateRepository] = None,
    ):
        self._settings = settings
        self._repository = repository
        # Optional, default None: a caller that predates FX-19 keeps working
        # unmodified — it just never links an applied-rate row.
        self._applied_rate_repository = applied_rate_repository
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread = threading.Thread(target=self._run, name="transactions", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._settings.transaction_consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.account_events_topic])
        LOG.info("consuming %s", self._settings.account_events_topic)
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
        if self._loop is None:
            LOG.warning("no loop bound; dropping transaction record")
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._apply(raw), self._loop)
            future.result(timeout=_WRITE_TIMEOUT_SECONDS)
        except Exception as error:  # noqa: BLE001 - one bad row must not kill the consumer
            LOG.error("failed to project transaction: %s", error)

    @staticmethod
    def _parse(raw) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as error:
            LOG.warning("dropping malformed transaction record: %s", error)
            return None
        if not isinstance(payload, dict):
            LOG.warning("dropping malformed transaction record: not an object")
            return None
        return payload

    async def _apply(self, raw) -> None:
        event = self._parse(raw)
        if event is None:
            return
        row_type = _EVENT_TO_ROW_TYPE.get(event.get("type"))
        if row_type is None:
            # `transfer_requested`, or anything unrecognised: not our concern.
            return
        try:
            await self._insert_for(row_type, event)
        except (KeyError, TypeError, ValueError) as error:
            LOG.warning("dropping malformed transaction record: %s", error)

    async def _insert_for(self, row_type: str, event: Dict[str, Any]) -> None:
        if row_type == "debit":
            counterparty = event["destination_account"]
        elif row_type == "credit":
            counterparty = event["source_account"]
        else:
            counterparty = event["destination_account"]

        applied_rate_id = await self._resolve_applied_rate_id(row_type, event)

        await self._repository.insert(
            request_id=uuid.UUID(str(event["request_id"])),
            account_number=event["account_id"],
            type=row_type,
            amount=event["amount"],
            counterparty_account=counterparty,
            decline_reason=event.get("reason") if row_type == "declined" else None,
            ts=self._parse_ts(event.get("ts")),
            applied_rate_id=applied_rate_id,
        )

    async def _resolve_applied_rate_id(
        self, row_type: str, event: Dict[str, Any]
    ) -> Optional[uuid.UUID]:
        """A row carrying `conversion` gets its applied-rate linked regardless
        of leg direction; ordinary debit legs never carry `conversion` so this
        is unchanged for existing transfer behavior (FX-19 extended for
        Phase 3: a cross-currency card payment's DEBIT-leg `outgoing_payment`
        is the first debit-side event to ever set `conversion`, attached by
        `account-service/domain.py`'s widened `_outgoing()`)."""
        if self._applied_rate_repository is None:
            return None
        conversion = event.get("conversion")
        if conversion is None:
            return None
        new_id = await self._applied_rate_repository.insert(
            pair=conversion["pair"],
            mid_rate=conversion["mid_rate"],
            applied_rate=conversion["applied_rate"],
            margin=conversion["margin"],
            direction=conversion["direction"],
            source_ts=self._parse_ts(conversion["source_ts"]),
        )
        return uuid.UUID(str(new_id))

    @staticmethod
    def _parse_ts(raw_ts: Any) -> datetime:
        if not isinstance(raw_ts, str) or not raw_ts:
            raise ValueError(f"malformed ts: {raw_ts!r}")
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
