"""Contract for `card_movements` persistence (Phase 2 purchases).

`typing.Protocol`, not `abc.ABC` — same convention as `ICardRepository`.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from ....domain.model import CardMovement


@runtime_checkable
class ICardMovementRepository(Protocol):
    async def insert(self, movement: CardMovement) -> CardMovement:
        """Insert one row, idempotent on `(request_id, movement_type)`
        (`ON CONFLICT DO NOTHING`, same guarantee `ITransactionRepository`
        documents) — a redelivered event is a silent no-op, not an error."""
        ...

    async def get_by_card_id(self, card_id: UUID) -> List[CardMovement]: ...
