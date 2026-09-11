"""Statement close + due-date orchestration (Credit Cards Phase 4).

Plain domain object: no FastAPI, no Depends, no import from `api` — same
convention as `card_account_service.py`. `close_statement`/`run_due_date_check`
take an explicit `period_end`/`today` parameter and never call `date.today()`
internally, so `batch/run_once.py`'s `check_and_close_if_due` can pass a
synthetic target date for downtime recovery (design's single most
safety-critical rule for this phase).

All money math is `Decimal`, quantized to 2dp with `ROUND_HALF_UP` — never a
bare `round()` — matching the `Numeric(14,2)` convention used everywhere else
in the card domain (`card_accounts.credit_limit`, `card_movements.amount`,
`installments.amount`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from . import money as money_service
from ..model import CardMovementType, Installment, Statement
from ...infra.database.interfaces.card_movement_repository import ICardMovementRepository
from ...infra.database.interfaces.card_repository import ICardRepository
from ...infra.database.interfaces.installment_repository import IInstallmentRepository
from ...infra.database.interfaces.statement_repository import IStatementRepository
from ...infra.pdf.statement_pdf_generator import render as render_statement_pdf


@dataclass(frozen=True)
class DueDateCheckSummary:
    """Outcome of one `run_due_date_check` run. The hourly batch cron
    (`batch/run_once.py`) ignores this return value — it only needs the side
    effects — but the admin manual-trigger endpoint
    (`api/v1/routers/batch_router.py`) reports it back to the caller instead
    of re-deriving the same counts by re-querying statements afterward."""

    finalized_count: int
    late_fees_applied_count: int


class StatementService:
    def __init__(
        self,
        statement_repository: IStatementRepository,
        card_movement_repository: ICardMovementRepository,
        installment_repository: IInstallmentRepository,
        card_repository: ICardRepository,
        *,
        credit_card_apr: Decimal,
        late_fee_amount: Decimal,
        minimum_payment_rate: Decimal,
        due_date_offset_days: int,
    ):
        self._statements = statement_repository
        self._card_movements = card_movement_repository
        self._installments = installment_repository
        self._cards = card_repository
        self._apr = credit_card_apr
        self._late_fee_amount = late_fee_amount
        self._minimum_payment_rate = minimum_payment_rate
        self._due_date_offset_days = due_date_offset_days

    async def close_statement(self, card_account_id: UUID, period_end: date) -> Optional[Statement]:
        """Idempotent: the `exists_for_period` guard is checked FIRST, before
        any other work, so calling this every hour from the batch worker
        never double-closes (design's #1 correctness rule)."""
        if await self._statements.exists_for_period(card_account_id, period_end):
            return await self._statements.get_latest(card_account_id)

        previous = await self._statements.get_latest(card_account_id)
        period_start = (
            previous.period_end + timedelta(days=1) if previous is not None
            else period_end - timedelta(days=30)
        )

        unpaid_previous_balance = Decimal("0")
        credit_balance_carried = Decimal("0")
        if previous is not None:
            diff = previous.total_due - previous.paid_amount
            if diff > 0:
                unpaid_previous_balance = diff
            elif diff < 0:
                credit_balance_carried = -diff

        purchases_total = await self._card_movements.sum_single_charge_purchases(
            card_account_id, period_start, period_end
        )
        billed_installments: List[Installment] = await self._installments.get_next_due_per_plan(
            card_account_id
        )
        for installment in billed_installments:
            purchases_total += installment.amount

        interest_total = Decimal("0")
        if unpaid_previous_balance > 0:
            interest_total = money_service.quantize(unpaid_previous_balance * self._apr / 12)

        late_fees_total = Decimal("0")
        total_due = purchases_total + interest_total + late_fees_total + unpaid_previous_balance - credit_balance_carried
        if total_due < 0:
            total_due = Decimal("0")

        minimum_payment = money_service.clamp(
            money_service.quantize(total_due * self._minimum_payment_rate), low=Decimal("0"), high=total_due
        )

        due_date = period_end + timedelta(days=self._due_date_offset_days)
        statement = await self._statements.create(
            card_account_id, period_start, period_end, due_date,
            purchases_total=purchases_total, interest_total=interest_total,
            total_due=total_due, credit_balance=credit_balance_carried,
            late_fees_total=late_fees_total, minimum_payment=minimum_payment,
        )

        for installment in billed_installments:
            await self._installments.mark_billed(installment.id, statement.id)

        # Pure formatting, no business computation — failures here must
        # never break the close (design: F3's acceptance bar is "does not
        # raise", no storage location specified yet).
        render_statement_pdf(statement, [], billed_installments)

        return statement

    async def run_due_date_check(self, today: date) -> DueDateCheckSummary:
        """Independent `paid_in_full`/`paid_by_due_date` thresholds, finalized
        exactly once per statement, with a capped late fee inserted only when
        `paid_by_due_date` is false."""
        due_statements = await self._statements.list_with_due_date(today, outcome_not_finalized=True)
        late_fees_applied_count = 0
        for statement in due_statements:
            paid_amount = await self._card_movements.sum_payments(
                statement.card_account_id, statement.period_start, today
            )
            paid_in_full = paid_amount >= statement.total_due
            paid_by_due_date = paid_amount >= statement.minimum_payment

            await self._statements.finalize_due_date_outcome(
                statement.id, paid_amount=paid_amount,
                paid_in_full=paid_in_full, paid_by_due_date=paid_by_due_date,
            )

            if not paid_by_due_date:
                late_fee = min(self._late_fee_amount, statement.minimum_payment)
                if late_fee > 0 and await self._insert_late_fee(statement, late_fee, today):
                    late_fees_applied_count += 1

        return DueDateCheckSummary(
            finalized_count=len(due_statements),
            late_fees_applied_count=late_fees_applied_count,
        )

    async def _insert_late_fee(self, statement: Statement, amount: Decimal, occurred_on: date) -> bool:
        """Returns whether a late-fee movement was actually inserted. False
        (no exception) means `_first_card_for` found no card for this
        account — that account is still finalized as `paid_by_due_date=False`
        by the caller either way, only the fee itself is skipped. The caller
        uses this to keep `DueDateCheckSummary.late_fees_applied_count`
        accurate rather than counting an attempt that silently no-opped."""
        # Imported here (not at module top) to avoid a hard dependency from
        # this module on the exact `CardMovement` construction shape unless a
        # late fee actually needs inserting.
        from datetime import datetime, timezone
        import uuid

        from ..model import CardMovement

        card = await self._first_card_for(statement.card_account_id)
        if card is None:
            return False
        await self._card_movements.insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card, request_id=uuid.uuid4(),
                movement_type=CardMovementType.LATE_FEE, amount=amount, currency="USD",
                created_at=datetime.combine(occurred_on, datetime.min.time(), tzinfo=timezone.utc),
                occurred_at=datetime.combine(occurred_on, datetime.min.time(), tzinfo=timezone.utc),
                description=f"Late fee for statement due {statement.due_date.isoformat()}",
            )
        )
        return True

    async def _first_card_for(self, card_account_id: UUID) -> Optional[UUID]:
        card = await self._cards.get_active_for_account(card_account_id)
        return card.id if card is not None else None
