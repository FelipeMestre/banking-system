"""Contract for `installments` persistence (Phase 2 purchases).

`typing.Protocol`, not `abc.ABC` — same convention as `ICardMovementRepository`.
"""
from __future__ import annotations

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
