"""Contract for the transactions read model (spec §3).

Write side is deliberately narrow: `insert` is the only mutator, and it is
idempotent by construction — the caller (`TransactionConsumer`) never has to
check for a duplicate itself, because `(request_id, account_number, type)`
already is the row's identity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ....domain.model import Transaction


class ITransactionRepository(Protocol):
    async def insert(
        self,
        *,
        request_id: UUID,
        account_number: str,
        type: str,
        amount: int,
        counterparty_account: str | None,
        decline_reason: str | None,
        ts: datetime,
        applied_rate_id: UUID | None = None,
        description: str | None = None,
    ) -> UUID | None:
        """Insert one row. A redelivered `(request_id, account_number, type)`
        is a silent no-op, not an error (spec §3.2).

        `applied_rate_id` links to the `applied_rates` audit row for a leg
        that carried a currency conversion (FX-16); `None` for every
        same-currency, outgoing, or declined row."""
        ...

    async def list_by_account(
        self,
        account_number: str,
        *,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[Transaction]:
        """Up to `limit` rows, newest first (`ts DESC, id DESC`).

        `before` is an exclusive keyset cursor: only rows strictly older than
        that `(ts, id)` pair are returned. Keyset, not offset, so a concurrent
        insert during pagination cannot skip or repeat a row (spec §3.3).
        """
        ...

    async def set_applied_rate(
        self, transaction_id: UUID, applied_rate_id: UUID
    ) -> None:
        """Link a transaction row to an applied_rates audit row (deposit cross-currency)."""
        ...
