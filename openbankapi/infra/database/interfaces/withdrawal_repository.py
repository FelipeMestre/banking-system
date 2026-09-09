"""Contract for the withdrawals audit table (admin-cash-withdrawals).

One audit row per `transactions` withdrawal movement. `movement_id` is the
FK and the `ON CONFLICT` target — duplicate inserts for the same movement
are idempotent no-ops.
"""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID


class IWithdrawalRepository(Protocol):
    async def insert(
        self,
        *,
        movement_id: UUID,
        admin_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Insert one withdrawals row.

        A redelivered `movement_id` is a silent no-op (`ON CONFLICT DO NOTHING`).
        """
        ...
