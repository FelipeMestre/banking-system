"""The account creation domain event (spec §7.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountCreated:
    """Raised when a `account` row is created.

    Not published to `account-events`: §5 defines the complete set of record
    types on that topic and this is not one of them, so emitting it would put a
    shape there that the ledger never declared. It exists as an in-process
    audit value and as the seam where a future outbox or CDC feed would attach.
    """

    account_number: str
    customer_id: str
    branch_id: str
    currency: str
    ts: str
