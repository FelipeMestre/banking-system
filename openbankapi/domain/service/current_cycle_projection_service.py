"""Live, never-persisted current-cycle projection for credit-card accounts.

Sits beside `StatementService` (not a method on it) so the "persists a close"
invariant `StatementService` owns stays separate from this service's
opposite invariant: `project()` MUST NEVER write anything, it only reads and
computes fresh figures on every call.

The single most safety-critical rule here (per design): whether the previous
statement's outstanding balance is derived from a LIVE `sum_payments` call or
from the statement's own frozen `paid_amount` field depends entirely on
whether `run_due_date_check` has already finalized that statement
(`status != CLOSED`). Getting this branch wrong either shows a stale
"already paid" balance as still overdue, or (worse) trusts a frozen
`paid_amount` that predates a payment the customer already made.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from . import cycle_dates
from . import money as money_service
from ..model import StatementStatus
from ...infra.database.interfaces.card_account_repository import ICardAccountRepository
from ...infra.database.interfaces.card_movement_repository import ICardMovementRepository
from ...infra.database.interfaces.installment_repository import IInstallmentRepository
from ...infra.database.interfaces.statement_repository import IStatementRepository

_ZERO = Decimal("0")


@dataclass(frozen=True)
class CurrentCycleProjection:
    card_account_id: UUID
    period_start: date
    projected_period_end: date
    overdue_from_previous_cycle: Optional[Decimal]
    interest_on_overdue: Optional[Decimal]
    new_purchases_this_cycle: Decimal
    total_to_pay: Decimal
    is_payable: bool = True


class CurrentCycleProjectionService:
    def __init__(
        self,
        statement_repository: IStatementRepository,
        card_movement_repository: ICardMovementRepository,
        installment_repository: IInstallmentRepository,
        card_account_repository: ICardAccountRepository,
        *,
        credit_card_apr: Decimal,
        close_day: int,
    ):
        self._statements = statement_repository
        self._card_movements = card_movement_repository
        self._installments = installment_repository
        self._card_accounts = card_account_repository
        self._apr = credit_card_apr
        self._close_day = close_day

    async def project(self, card_account_id: UUID, today: date) -> CurrentCycleProjection:
        previous = await self._statements.get_latest(card_account_id)
        if previous is not None:
            period_start = previous.period_end + timedelta(days=1)
        else:
            issuance_date = await self._card_accounts.get_issuance_date(card_account_id)
            period_start = issuance_date

        projected_period_end = cycle_dates.next_close_date_after(period_start, self._close_day)

        overdue: Optional[Decimal] = None
        interest: Optional[Decimal] = None
        if previous is not None and today > previous.due_date:
            if previous.status == StatementStatus.CLOSED:
                paid = await self._card_movements.sum_payments(
                    card_account_id, previous.period_start, today
                )
            else:
                paid = previous.paid_amount
            outstanding = previous.total_due - paid
            if outstanding > 0:
                overdue = outstanding
                interest = money_service.quantize(outstanding * self._apr / 12)

        purchases = await self._card_movements.sum_single_charge_purchases(
            card_account_id, period_start, today
        )
        for installment in await self._installments.get_next_due_per_plan(card_account_id):
            purchases += installment.amount

        total = purchases + (overdue or _ZERO) + (interest or _ZERO)

        return CurrentCycleProjection(
            card_account_id=card_account_id,
            period_start=period_start,
            projected_period_end=projected_period_end,
            overdue_from_previous_cycle=overdue,
            interest_on_overdue=interest,
            new_purchases_this_cycle=purchases,
            total_to_pay=total,
        )
