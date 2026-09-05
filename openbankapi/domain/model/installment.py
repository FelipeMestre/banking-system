"""One installment of a card movement — Phase 2 (billing assignment is Phase 4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class InstallmentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"


@dataclass(frozen=True)
class Installment:
    id: UUID
    card_movement_id: UUID
    installment_number: int
    amount: Decimal
    due_date: date
    status: InstallmentStatus
    created_at: datetime
