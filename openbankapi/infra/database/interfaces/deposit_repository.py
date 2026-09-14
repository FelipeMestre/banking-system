"""Contract for the deposits audit table (admin-cash-deposits).

One audit row per `transactions` deposit movement. `movement_id` is the
FK and the `ON CONFLICT` target — duplicate inserts for the same movement
are idempotent no-ops.
"""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID


class IDepositRepository(Protocol):
    async def insert(
        self,
        *,
        movement_id: UUID,
        admin_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Insert one deposits row.

        A redelivered `movement_id` is a silent no-op (`ON CONFLICT DO NOTHING`).
        """
        ...
