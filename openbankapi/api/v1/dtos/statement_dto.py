"""Billing-cycle (statement) DTOs — Credit Cards `credit-card-monthly-batch-
statements` frontend page.

`StatementDTO` mirrors the `Statement` domain model field-for-field: the
frontend billing-cycle tab strip derives its status label
(`open`/`still open`/`paid in full`/`paid minimum, not full`/`missed minimum,
late fee applied`) itself from `status`/`paid_in_full`/`paid_by_due_date`, so
nothing here pre-computes that label — same "expose raw state, let the
consumer decide" pattern as `CardMovementDTO`.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class StatementDTO(BaseModel):
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
    status: str
    created_at: datetime
    updated_at: datetime
    payable: bool

    model_config = {"from_attributes": True}


class InstallmentPayoffDTO(BaseModel):
    """The "settle all installment balances early" figure — a plain sum of
    still-unbilled installment amounts, safe to expose verbatim because
    installments carry 0% interest (Phase 2's confirmed decision), so there
    is no unearned-interest or fee-waiver figure to guess at."""

    card_account_id: UUID
    payoff_amount: Decimal
    currency: str = "USD"
