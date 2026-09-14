"""Used-credit approximation + movements-list DTOs (`credit-cards-frontend-page`).

`UsedCreditEstimateDTO.is_estimate` is the honesty signal the spec requires:
this figure is a derived approximation from `card_movements`, never the
Flink Card Service's authoritative `used_credit` state, and both the
response and the frontend UI must label it as such.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UsedCreditEstimateDTO(BaseModel):
    card_account_id: UUID
    used_credit_estimate: Decimal = Field(ge=0)
    credit_limit: Decimal
    currency: str = "USD"
    is_estimate: bool = True
    movement_count: int = Field(ge=0)


class CardMovementDTO(BaseModel):
    id: UUID
    movement_type: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    description: Optional[str] = None
    decline_reason: Optional[str] = None
    fx_pair: Optional[str] = None
    fx_applied_rate: Optional[Decimal] = None
    installment_count: Optional[int] = None
    installment_amount: Optional[Decimal] = None
