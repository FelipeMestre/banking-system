"""Populates `card_movements`/`installments` off `card-events` (Credit Cards
Phase 2 — design §5).

Same thread/loop/`run_coroutine_threadsafe` shape as `TransactionConsumer`.
Only `purchase_approved`/`purchase_declined` are dispatched — `purchase_requested`
is not yet a resolved outcome, the same reasoning `TransactionConsumer` applies
to `transfer_requested`.

`purchase_approved` optionally carries an `applied_rate` conversion dict
(`card-service/domain.py`'s `_approved`) — persisted to `applied_rates` first
via `IAppliedRateRepository`, the same FX-19 pattern `TransactionConsumer`
uses for `incoming_payment`'s `conversion`. `ICardMovementRepository.insert`
is idempotent by construction (`ON CONFLICT (request_id, movement_type) DO
NOTHING`), so at-least-once redelivery never needs its own dedup check for
the movement row itself.

Installments are a second write the movement's ON CONFLICT dedup does not
cover: a redelivered `purchase_approved` must not double-insert them. Rather
than track freshness through `insert`'s return value (which cannot
distinguish "just inserted" from "already existed" — see
`postgres_card_movement_repository.py`), this consumer checks
`get_by_movement_id` before splitting: any existing rows mean this movement
was already fully materialised, so the split is skipped.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from confluent_kafka import Consumer, KafkaError

from ....config import Settings
from ....domain.model import CardMovement, CardMovementType, Installment, InstallmentStatus
from ....domain.service.installment_service import split_into_installments
from ...database.interfaces.applied_rate_repository import IAppliedRateRepository
from ...database.interfaces.card_movement_repository import ICardMovementRepository
from ...database.interfaces.installment_repository import IInstallmentRepository

LOG = logging.getLogger("openbankapi.kafka.card_movements")

_WRITE_TIMEOUT_SECONDS = 30
_CENTS_PER_USD = Decimal(100)

_EVENT_TO_MOVEMENT_TYPE = {
    "purchase_approved": CardMovementType.PURCHASE,
    "purchase_declined": CardMovementType.DECLINED,
}


class CardMovementConsumer:
    def __init__(
        self,
        settings: Settings,
        movement_repository: ICardMovementRepository,
        installment_repository: IInstallmentRepository,
        applied_rate_repository: Optional[IAppliedRateRepository] = None,
    ):
        self._settings = settings
        self._movement_repository = movement_repository
        self._installment_repository = installment_repository
        # Optional, default None: mirrors `TransactionConsumer` — a caller
        # that never wires one just never links an applied-rate row.
        self._applied_rate_repository = applied_rate_repository
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread = threading.Thread(target=self._run, name="card-movements", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": self._settings.bootstrap_servers,
                "group.id": self._settings.card_movement_consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self._settings.card_events_topic])
        LOG.info("consuming %s", self._settings.card_events_topic)
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
            LOG.warning("no loop bound; dropping card movement record")
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._apply(raw), self._loop)
            future.result(timeout=_WRITE_TIMEOUT_SECONDS)
        except Exception as error:  # noqa: BLE001 - one bad row must not kill the consumer
            LOG.error("failed to project card movement: %s", error)

    @staticmethod
    def _parse(raw) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as error:
            LOG.warning("dropping malformed card movement record: %s", error)
            return None
        if not isinstance(payload, dict):
            LOG.warning("dropping malformed card movement record: not an object")
            return None
        return payload

    async def _apply(self, raw) -> None:
        event = self._parse(raw)
        if event is None:
            return
        movement_type = _EVENT_TO_MOVEMENT_TYPE.get(event.get("type"))
        if movement_type is None:
            # `purchase_requested`, or anything unrecognised: not our concern.
            return
        try:
            await self._insert_for(movement_type, event)
        except (KeyError, TypeError, ValueError) as error:
            LOG.warning("dropping malformed card movement record: %s", error)

    async def _insert_for(self, movement_type: CardMovementType, event: Dict[str, Any]) -> None:
        applied_rate_id = await self._resolve_applied_rate_id(movement_type, event)
        amount = Decimal(event["amount_usd"]) / _CENTS_PER_USD

        movement = CardMovement(
            id=uuid.uuid4(),
            card_id=uuid.UUID(str(event["card_id"])),
            request_id=uuid.UUID(str(event["request_id"])),
            movement_type=movement_type,
            amount=amount,
            currency="USD",
            created_at=self._parse_ts(event.get("ts")),
            decline_reason=event.get("decline_reason") if movement_type == CardMovementType.DECLINED else None,
            applied_rate_id=applied_rate_id,
            occurred_at=self._parse_ts(event.get("ts")),
        )
        inserted = await self._movement_repository.insert(movement)

        if movement_type == CardMovementType.PURCHASE and event.get("installments", 1) > 1:
            await self._split_installments(inserted, event["installments"])

    async def _split_installments(self, movement: CardMovement, count: int) -> None:
        # A redelivered `purchase_approved` re-runs this method; `insert`'s
        # ON CONFLICT dedup means `movement` may be either the freshly
        # inserted row or a pre-existing one — either way, existing
        # installment rows mean the split already happened.
        already_split = await self._installment_repository.get_by_movement_id(movement.id)
        if already_split:
            return

        due_dates: List[date] = [movement.occurred_at.date() for _ in range(count)]
        amounts = split_into_installments(movement.amount, count, due_dates)
        installments = [
            Installment(
                id=uuid.uuid4(),
                card_movement_id=movement.id,
                installment_number=index + 1,
                amount=amounts[index],
                due_date=due_dates[index],
                status=InstallmentStatus.PENDING,
                created_at=movement.created_at,
            )
            for index in range(count)
        ]
        await self._installment_repository.bulk_insert(installments)

    async def _resolve_applied_rate_id(
        self, movement_type: CardMovementType, event: Dict[str, Any]
    ) -> Optional[uuid.UUID]:
        """Only `purchase_approved` ever carries `applied_rate`; a decline
        never does (`card-service/domain.py`'s `_declined` never sets it)."""
        if movement_type != CardMovementType.PURCHASE or self._applied_rate_repository is None:
            return None
        conversion = event.get("applied_rate")
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
