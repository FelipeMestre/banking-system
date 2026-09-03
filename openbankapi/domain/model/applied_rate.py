"""One persisted margin-adjustment audit row (FX-14). Built, not yet written to
by any route in this phase — see `IAppliedRateRepository`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class AppliedRate:
    id: UUID
    pair: str
    mid_rate: Decimal
    applied_rate: Decimal
    margin: Decimal
    direction: str
    source_ts: datetime
    created_at: datetime
