"""Contract for the transactions read model (spec §3).

Write side is deliberately narrow: `insert` is the only mutator, and it is
idempotent by construction — the caller (`TransactionConsumer`) never has to
check for a duplicate itself, because `(request_id, account_number, type)`
already is the row's identity.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol, Tuple
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
        counterparty_account: str,
        decline_reason: Optional[str],
        ts: datetime,
    ) -> None:
        """Insert one row. A redelivered `(request_id, account_number, type)`
        is a silent no-op, not an error (spec §3.2)."""
        ...

    async def list_by_account(
        self,
        account_number: str,
        *,
        limit: int,
        before: Optional[Tuple[datetime, UUID]] = None,
    ) -> List[Transaction]:
        """Up to `limit` rows, newest first (`ts DESC, id DESC`).

        `before` is an exclusive keyset cursor: only rows strictly older than
        that `(ts, id)` pair are returned. Keyset, not offset, so a concurrent
        insert during pagination cannot skip or repeat a row (spec §3.3).
        """
        ...
