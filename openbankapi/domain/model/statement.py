"""A card account's billing period — Phase 4 completes what Phase 1 only
structured: totals, thresholds and the derived-from-`total_due`/`paid_amount`
carried-balance math live in `domain/service/statement_service.py`, not here.
This dataclass only carries state, matching every other domain entity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class StatementStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PAID = "paid"
    OVERDUE = "overdue"


@dataclass(frozen=True)
class Statement:
    id: UUID
    card_account_id: UUID
    period_start: date
    period_end: date
    due_date: date
    purchases_total: Decimal
    interest_total: Decimal
    total_due: Decimal
    paid_amount: Decimal
    credit_balance: Decimal
    late_fees_total: Decimal
    minimum_payment: Decimal
    paid_in_full: bool
    paid_by_due_date: bool
    status: StatementStatus
    created_at: datetime
    updated_at: datetime
