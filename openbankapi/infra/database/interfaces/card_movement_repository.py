"""Contract for `card_movements` persistence (Phase 2 purchases).

`typing.Protocol`, not `abc.ABC` — same convention as `ICardRepository`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
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

    async def get_by_card_account_id(self, card_account_id: UUID) -> List[CardMovement]:
        """All movements ever posted against every card (active or replaced)
        ever issued under this card_account, newest first. Spans renewals —
        this is the source of truth for a customer-facing 'one card' history."""
        ...

    async def sum_single_charge_purchases(
        self, card_account_id: UUID, period_start: date, period_end: date
    ) -> Decimal:
        """Sum of `purchase` movements in `[period_start, period_end]` that
        are NOT part of an installment plan (Phase 4 `close_statement`).
        Joins `card_movements -> cards` on `card_id`, mirroring
        `get_by_card_account_id`'s real join shape."""
        ...

    async def sum_by_type(
        self, card_account_id: UUID, movement_type: str, period_start: date, period_end: date
    ) -> Decimal:
        """Sum of movements of `movement_type` in `[period_start, period_end]`."""
        ...

    async def sum_payments(self, card_account_id: UUID, period_start: date, period_end: date) -> Decimal:
        """Sum of `payment` movements in `[period_start, period_end]`."""
        ...

    async def compute_current_balance(self, card_account_id: UUID) -> Decimal:
        """Current outstanding balance across every movement ever posted
        (single SQL `SUM(CASE ...)`, not an app-level loop — design D3):
        `purchase`/`fee`/`interest`/`late_fee` increase it, `payment`/`refund`
        decrease it, everything else is ignored. `Decimal("0.00")` when the
        account has no movements at all."""
        ...
