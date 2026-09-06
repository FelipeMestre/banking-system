"""Contract for `installments` persistence (Phase 2 purchases).

`typing.Protocol`, not `abc.ABC` — same convention as `ICardMovementRepository`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Protocol, runtime_checkable
from uuid import UUID

from ....domain.model import Installment


@runtime_checkable
class IInstallmentRepository(Protocol):
    async def bulk_insert(self, installments: List[Installment]) -> None:
        """Insert every row in one batch. Called only after the parent
        `card_movements` row exists, since each installment FKs to it."""
        ...

    async def get_by_movement_id(self, movement_id: UUID) -> List[Installment]: ...

    async def get_by_statement_id(self, statement_id: UUID) -> List[Installment]:
        """Every installment billed onto this exact statement — the inverse
        of `mark_billed` (Credit Cards `credit-card-monthly-batch-statements`
        frontend page). Powers the cycle-scoped movements list and the real
        statement PDF download: both need to know exactly which installments
        this specific closed cycle billed, not just the lowest-unbilled one
        `get_next_due_per_plan` returns."""
        ...

    async def sum_unbilled(self, card_account_id: UUID) -> Decimal:
        """Sum of `amount` across every installment for this account's cards
        with `statement_id IS NULL` — every remaining installment balance
        across every plan, not just the next-due one per plan. This is a
        plain aggregate over already-known, unambiguous state (unlike an
        "early payoff" figure that would need to guess at unearned-interest
        or fee waivers, which nothing in this domain computes) — safe to
        expose as the "settle all installment balances early" amount."""
        ...

    async def get_next_due_per_plan(self, card_account_id: UUID) -> List[Installment]:
        """Lowest unbilled `installment_number` per plan (`card_movement_id`)
        for this account — `DISTINCT ON (card_movement_id) ... WHERE
        statement_id IS NULL ORDER BY card_movement_id, installment_number ASC`.
        This is what makes installments bill exactly one at a time."""
        ...

    async def mark_billed(self, installment_id: UUID, statement_id: UUID) -> None:
        """Set `statement_id`, taking this installment out of future
        `get_next_due_per_plan` results."""
        ...

    async def get_total_installments(self, card_movement_id: UUID) -> int:
        """`MAX(installment_number)` for this plan — derived at read time,
        never stored as a column, so it stays correct regardless of how
        many installments have already been billed."""
        ...
