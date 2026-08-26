"""Account creation orchestration (spec §3.5, §8.2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from ...config import Settings
from ..model import Cuenta


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CuentaService:
    def __init__(self, settings: Settings, repository, publisher):
        self._settings = settings
        self._repository = repository
        self._publisher = publisher

    async def open_account(
        self, *, moneda: str, cliente_id: UUID, sucursal_id: UUID
    ) -> Cuenta:
        """Create the account row.

        No opening balance is written here, ever. A new account starts at 0 on
        both sides with no synchronisation needed: Postgres defaults `saldo` to
        0, and Flink lazily initialises an account's keyed state to 0 the first
        time it sees any event for that key. They agree at t=0 for free.
        """
        return await self._repository.create(
            moneda=moneda, cliente_id=cliente_id, sucursal_id=sucursal_id
        )

    def credit_opening_balance(self, numero_cuenta: str, amount: int) -> Dict[str, Any]:
        """Give an account a non-zero opening balance the event-sourced way.

        Never a direct UPDATE on `cuentas.saldo` (spec §3.5). The credit takes
        the same path as every other credit in the system: an `incoming_payment`
        on `account-events`, which Flink applies and then announces back through
        `account-balances`. The read model updates as a consequence, not as a
        separate write.
        """
        event = {
            "type": "incoming_payment",
            "request_id": f"seed-{uuid.uuid4()}",
            "account_id": numero_cuenta,
            "amount": amount,
            "leg": "credit:seed",
            "ts": _now(),
        }
        self._publisher.publish(
            topic=self._settings.account_events_topic,
            key=numero_cuenta,
            value=event,
        )
        return event
