"""The account creation domain event (spec §7.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountCreated:
    """Raised when a `cuenta` row is created.

    Not published to `account-events`: §5 defines the complete set of record
    types on that topic and this is not one of them, so emitting it would put a
    shape there that the ledger never declared. It exists as an in-process
    audit value and as the seam where a future outbox or CDC feed would attach.
    """

    numero_cuenta: str
    cliente_id: str
    sucursal_id: str
    moneda: str
    ts: str
