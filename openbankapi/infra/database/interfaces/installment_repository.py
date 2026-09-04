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
