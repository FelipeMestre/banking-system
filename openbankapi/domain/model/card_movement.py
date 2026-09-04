"""A card ledger entry — purchase, decline, or (later) payment/fee/interest/refund."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class CardMovementType(str, Enum):
    PURCHASE = "purchase"
    PAYMENT = "payment"
    FEE = "fee"
    INTEREST = "interest"
    REFUND = "refund"
    DECLINED = "declined"


@dataclass(frozen=True)
class CardMovement:
    id: UUID
    card_id: UUID
    request_id: UUID
    movement_type: CardMovementType
    amount: Decimal
    currency: str
    created_at: datetime
    description: Optional[str] = None
    decline_reason: Optional[str] = None
    applied_rate_id: Optional[UUID] = None
    occurred_at: Optional[datetime] = None
