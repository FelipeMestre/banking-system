"""Contract for `applied_rates` persistence (FX-14).

`typing.Protocol`, not `abc.ABC` — matches this codebase's real convention
(`IAccountRepository`, `IBranchRepository`), not the ABC wording in the
proposal's literal spec text.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


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
