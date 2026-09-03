"""The transfer use case (spec §8.1, extended by FX-17).

The write-path shape is unchanged from v1: ONE atomic append and return, never
waiting on the ledger — the only question that gates a transfer, "are there
funds?", can only be answered by Flink. What changed in this phase is that a
cross-currency transfer needs to know both accounts' currencies to resolve a
margin-adjusted conversion quote before publishing, so `request_transfer` now
reads `IAccountRepository` (reference data, not the ledger) and, when needed,
`ForeignExchangeCacheService`. If either account is unknown, conversion is
skipped entirely and the event keeps its pre-Phase-3 shape — this service
never blocks a transfer on reference data it cannot resolve.

Plain domain object: no FastAPI, no Depends, no import from `api` or `infra`
concrete adapters (only their interfaces/services, injected as constructor
dependencies). Per the architecture doc, the domain layer must never depend on
any other layer — its Dep wiring lives in `config/dependencies.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...config import Settings
from ...infra.cache.services.foreign_exchange_cache_service import ForeignExchangeCacheService
from ...infra.database.interfaces.account_repository import IAccountRepository
from ...infra.kafka.interfaces.event_publisher import IEventPublisher
from ..events import TransferRequested
from .conversion_service import convert


def compute_fee(amount: int, flat_fee_cents: int) -> int:
    """A flat fee, never larger than the amount being transferred.

    Capping at `amount` keeps the fee from quietly exceeding the transfer on
    very small payments, which would make the total debit more than double what
    the user asked to send.
    """
    return min(max(flat_fee_cents, 0), amount)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def to_wire(
    event: TransferRequested,
    *,
    destination_amount: Optional[int] = None,
    applied_rate: Optional[dict] = None,
    fee_amount_usd: Optional[int] = None,
    fee_applied_rate: Optional[dict] = None,
    add_conversion_fields: bool = False,
) -> Dict[str, Any]:
    """The §5 JSON shape, plus FX-17's additive conversion fields.

    `add_conversion_fields` gates whether `destination_amount`/`applied_rate`/
    `fee_amount_usd`/`fee_applied_rate` appear at all: they are added only
    when both accounts were resolvable (see `request_transfer`), so a
    transfer between accounts this service cannot look up keeps the exact
    pre-Phase-3 wire shape (FX-20 scope guard).
    """
    wire: Dict[str, Any] = {
        "type": "transfer_requested",
        "request_id": event.request_id,
        "source_account": event.source_account,
        "destination_account": event.destination_account,
        "fees_account": event.fees_account,
        "amount": event.amount,
        "fee_amount": event.fee_amount,
        "ts": event.ts,
    }
    if add_conversion_fields:
        wire["destination_amount"] = (
            destination_amount if destination_amount is not None else event.amount
        )
        wire["applied_rate"] = applied_rate
        wire["fee_amount_usd"] = (
            fee_amount_usd if fee_amount_usd is not None else event.fee_amount
        )
        wire["fee_applied_rate"] = fee_applied_rate
    return wire


class TransferService:
    def __init__(
        self,
        settings: Settings,
        publisher: IEventPublisher,
        account_repository: IAccountRepository,
        foreign_exchange_cache_service: ForeignExchangeCacheService,
    ):
        self._settings = settings
        self._publisher = publisher
        self._account_repository = account_repository
        self._foreign_exchange_cache_service = foreign_exchange_cache_service

    async def request_transfer(
        self, source_account: str, destination_account: str, amount: int
    ) -> TransferRequested:
        """Append the request and return. Never waits on the ledger.

        Reads `IAccountRepository` — reference data, not the ledger — purely
        to resolve currencies for a conversion quote. A gate on "are there
        funds?" still only ever comes from Flink; this lookup never blocks or
        declines a transfer, it only decides whether the event needs
        additive conversion fields at all.
        """
        event = TransferRequested(
            request_id=str(uuid.uuid4()),
            source_account=source_account,
            destination_account=destination_account,
            fees_account=self._settings.fees_account,
            amount=amount,
            fee_amount=compute_fee(amount, self._settings.fee_flat_cents),
            ts=_now(),
        )

        wire_kwargs: Dict[str, Any] = {}
        source = await self._account_repository.get_by_account_number(source_account)
        destination = await self._account_repository.get_by_account_number(destination_account)
        if source is not None and destination is not None:
            wire_kwargs = await self._resolve_conversion(event, source.currency, destination.currency)
            wire_kwargs["add_conversion_fields"] = True

        # Keyed by source account: that is the shard whose balance guards the
        # transfer, so the request lands in the partition that will decide it.
        self._publisher.publish(
            topic=self._settings.account_events_topic,
            key=source_account,
            value=to_wire(event, **wire_kwargs),
        )
        return event

    async def _resolve_conversion(
        self, event: TransferRequested, source_currency: str, destination_currency: str
    ) -> Dict[str, Any]:
        needs_destination_conversion = source_currency != destination_currency
        needs_fee_conversion = source_currency != "USD"

        if not needs_destination_conversion and not needs_fee_conversion:
            return {}

        rates = await self._foreign_exchange_cache_service.get_rates()
        result: Dict[str, Any] = {}

        if needs_destination_conversion:
            destination_quote = convert(
                event.amount, source_currency, destination_currency, "credit", rates
            )
            result["destination_amount"] = destination_quote["final_amount"]
            result["applied_rate"] = destination_quote["applied_rate"]

        if needs_fee_conversion:
            # "debit" here, NOT "credit": this is the bank's own fee income,
            # so the margin must work against the bank, not for it — the
            # opposite of the destination leg above.
            fee_quote = convert(event.fee_amount, source_currency, "USD", "debit", rates)
            result["fee_amount_usd"] = fee_quote["final_amount"]
            result["fee_applied_rate"] = fee_quote["applied_rate"]

        return result