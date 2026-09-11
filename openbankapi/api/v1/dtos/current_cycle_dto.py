"""Live current-cycle projection DTO — `GET /card-accounts/{id}/current-cycle`.

`overdue_from_previous_cycle`/`interest_on_overdue` default to `None` and
MUST stay `None` (never serialized as `0`) whenever
`CurrentCycleProjectionService.project` returns them absent — that
distinction is the spec's own explicit acceptance criterion, not a cosmetic
default.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CurrentCycleResponseDTO(BaseModel):
    period_start: date
    projected_period_end: date
    overdue_from_previous_cycle: Optional[Decimal] = None
    interest_on_overdue: Optional[Decimal] = None
    new_purchases_this_cycle: Decimal
    total_to_pay: Decimal
    payable: bool = True

    model_config = {"from_attributes": True}
