"""Contract for `statements` persistence (Credit Cards Phase 4).

`typing.Protocol`, not `abc.ABC` — same convention as every other repository
interface in this codebase (`ICardMovementRepository`, `ICardAccountRepository`).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from ....domain.model import Statement


@runtime_checkable
class IStatementRepository(Protocol):
    async def exists_for_period(self, card_account_id: UUID, period_end: date) -> bool:
        """True when a statement for this exact `(card_account_id, period_end)`
        already exists. This is `close_statement`'s idempotency guard — it
        must be checked FIRST, before any other work, so calling the close
        loop every hour is safe and never double-closes."""
        ...

    async def get_latest(self, card_account_id: UUID) -> Optional[Statement]:
        """Most recently closed statement for this account, or `None` if
        none exists yet (first-ever close for this account)."""
        ...

    async def create(
        self,
        card_account_id: UUID,
        period_start: date,
        period_end: date,
        due_date: date,
        purchases_total: Decimal,
        interest_total: Decimal,
        total_due: Decimal,
        credit_balance: Decimal,
        late_fees_total: Decimal,
        minimum_payment: Decimal,
    ) -> Statement: ...

    async def list_with_due_date(self, due_date: date, outcome_not_finalized: bool) -> List[Statement]:
        """Statements whose `due_date` matches, optionally filtered to those
        `run_due_date_check` has not yet finalized (`paid_in_full`/
        `paid_by_due_date` both still at their default `False` with zero
        `paid_amount` is NOT the filter — finalization is tracked
        independently so a $0-paid statement can still be marked finalized)."""
        ...

    async def finalize_due_date_outcome(
        self, statement_id: UUID, paid_amount: Decimal, paid_in_full: bool, paid_by_due_date: bool
    ) -> None:
        """Persist the due-date outcome exactly once. Called by
        `run_due_date_check` after computing the two independent thresholds."""
        ...
