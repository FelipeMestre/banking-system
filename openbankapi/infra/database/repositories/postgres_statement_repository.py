"""Postgres implementation of `IStatementRepository` (Credit Cards Phase 4).

Finalization tracking reuses the existing `status` enum rather than adding a
new column: `create()` always writes `status='closed'`; `finalize_due_date_outcome`
moves it to `'paid'` or `'overdue'` (design's explicit "keep the existing
`status` enum, driven by the same finalize call" decision). That is what makes
`list_with_due_date(due_date, outcome_not_finalized=True)` a plain
`status == 'closed'` filter — a statement `run_due_date_check` already
finalized moves off `'closed'` and stops being selected the second time
(guards the double-finalize scenario).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from ....domain.model import Statement, StatementStatus
from ..schemas.models import StatementORM
from ._base import PostgresRepository


def _to_domain(row: StatementORM) -> Statement:
    return Statement(
        id=row.id,
        card_account_id=row.card_account_id,
        period_start=row.period_start,
        period_end=row.period_end,
        due_date=row.due_date,
        purchases_total=row.purchases_total,
        interest_total=row.interest_total,
        total_due=row.total_due,
        paid_amount=row.paid_amount,
        credit_balance=row.credit_balance,
        late_fees_total=row.late_fees_total,
        minimum_payment=row.minimum_payment,
        paid_in_full=row.paid_in_full,
        paid_by_due_date=row.paid_by_due_date,
        status=StatementStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresStatementRepository(PostgresRepository):
    async def exists_for_period(self, card_account_id: UUID, period_end: date) -> bool:
        row = await self._fetch_one(
            StatementORM,
            StatementORM.card_account_id == card_account_id,
            StatementORM.period_end == period_end,
        )
        return row is not None

    async def get_latest(self, card_account_id: UUID) -> Optional[Statement]:
        result = await self._session.execute(
            select(StatementORM)
            .where(StatementORM.card_account_id == card_account_id)
            .order_by(StatementORM.period_end.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_by_id(self, statement_id: UUID) -> Optional[Statement]:
        row = await self._fetch_one(StatementORM, StatementORM.id == statement_id)
        return _to_domain(row) if row else None

    async def list_by_card_account_id(self, card_account_id: UUID, limit: int) -> List[Statement]:
        result = await self._session.execute(
            select(StatementORM)
            .where(StatementORM.card_account_id == card_account_id)
            .order_by(StatementORM.period_end.desc())
            .limit(limit)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def create(
        self,
        card_account_id: UUID,
        period_start: date,
        period_end: date,
        due_date: date,
        purchases_total: Decimal,
        interest_total: Decimal,
        total_due: Decimal,
        credit_balance: Decimal,
        late_fees_total: Decimal,
        minimum_payment: Decimal,
    ) -> Statement:
        row = await self._insert(
            StatementORM,
            {
                "card_account_id": card_account_id,
                "period_start": period_start,
                "period_end": period_end,
                "due_date": due_date,
                "purchases_total": purchases_total,
                "interest_total": interest_total,
                "total_due": total_due,
                "credit_balance": credit_balance,
                "late_fees_total": late_fees_total,
                "minimum_payment": minimum_payment,
                "status": StatementStatus.CLOSED.value,
            },
        )
        return _to_domain(row)

    async def list_with_due_date(self, due_date: date, outcome_not_finalized: bool) -> List[Statement]:
        where = [StatementORM.due_date == due_date]
        if outcome_not_finalized:
            where.append(StatementORM.status == StatementStatus.CLOSED.value)
        result = await self._session.execute(select(StatementORM).where(*where))
        return [_to_domain(row) for row in result.scalars().all()]

    async def finalize_due_date_outcome(
        self, statement_id: UUID, paid_amount: Decimal, paid_in_full: bool, paid_by_due_date: bool
    ) -> None:
        new_status = StatementStatus.PAID if paid_in_full else StatementStatus.OVERDUE
        await self._update(
            StatementORM,
            StatementORM.id == statement_id,
            {
                "paid_amount": paid_amount,
                "paid_in_full": paid_in_full,
                "paid_by_due_date": paid_by_due_date,
                "status": new_status.value,
            },
        )
