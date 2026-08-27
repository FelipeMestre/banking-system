"""The transfer use case (spec §8.1).

Behaviour is unchanged from v1, deliberately. The spec says so, and there is a
reason worth stating: this is the write path. It performs ONE atomic append and
returns. It does not read Postgres, because making the payment path depend on
the reference-data database would reintroduce exactly the cross-system coupling
this architecture exists to avoid — and because the only question that actually
gates a transfer, "are there funds?", can only be answered by Flink.

Plain domain object: no FastAPI, no Depends, no import from `api` or `infra`.
Per the architecture doc, the domain layer must never depend on any other
layer — its Dep wiring lives in `config/dependencies.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from ...config import Settings
from ...infra.kafka.interfaces.event_publisher import IEventPublisher
from ..events import TransferRequested


def compute_fee(amount: int, flat_fee_cents: int) -> int:
    """A flat fee, never larger than the amount being transferred.

    Capping at `amount` keeps the fee from quietly exceeding the transfer on
    very small payments, which would make the total debit more than double what
    the user asked to send.
    """
    return min(max(flat_fee_cents, 0), amount)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def to_wire(event: TransferRequested) -> Dict[str, Any]:
    """The §5 JSON shape. The domain event itself knows nothing about this."""
    return {
        "type": "transfer_requested",
        "request_id": event.request_id,
        "source_account": event.source_account,
        "destination_account": event.destination_account,
        "fees_account": event.fees_account,
        "amount": event.amount,
        "fee_amount": event.fee_amount,
        "ts": event.ts,
    }


class TransferService:
    def __init__(self, settings: Settings, publisher: IEventPublisher):
        self._settings = settings
        self._publisher = publisher

    def request_transfer(
        self, source_account: str, destination_account: str, amount: int
    ) -> TransferRequested:
        """Append the request and return. Never waits on the ledger."""
        event = TransferRequested(
            request_id=str(uuid.uuid4()),
            source_account=source_account,
            destination_account=destination_account,
            fees_account=self._settings.fees_account,
            amount=amount,
            fee_amount=compute_fee(amount, self._settings.fee_flat_cents),
            ts=_now(),
        )
        # Keyed by source account: that is the shard whose balance guards the
        # transfer, so the request lands in the partition that will decide it.
        self._publisher.publish(
            topic=self._settings.account_events_topic,
            key=source_account,
            value=to_wire(event),
        )
        return event