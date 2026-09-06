"""Contract for `applied_rates` persistence (FX-14).

`typing.Protocol`, not `abc.ABC` — matches this codebase's real convention
(`IAccountRepository`, `IBranchRepository`), not the ABC wording in the
proposal's literal spec text.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import AppliedRate


class IAppliedRateRepository(Protocol):
    async def insert(
        self,
        *,
        pair: str,
        mid_rate: float,
        applied_rate: float,
        margin: float,
        direction: str,
        source_ts: datetime,
    ) -> str:
        """Persist one applied-rate audit row. Returns the new row's `id` as a UUID string."""
        ...

    async def get_by_id(self, applied_rate_id: UUID) -> Optional[AppliedRate]:
        """Read back one applied-rate audit row, used by the movements-list
        endpoint to display an FX purchase's original amount and rate."""
        ...
