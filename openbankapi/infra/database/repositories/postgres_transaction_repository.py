"""Postgres implementation of ITransactionRepository.

`insert` uses `ON CONFLICT DO NOTHING` rather than a pre-check SELECT — the
same time-of-check-to-time-of-use reasoning `errors.py` documents for other
repositories applies here too, and at-least-once Kafka delivery makes the race
routine rather than theoretical.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.model import Transaction, TransactionType
from ..schemas.models import TransactionORM
from ._base import PostgresRepository


def _to_domain(row: TransactionORM) -> Transaction:
    return Transaction(
        id=row.id,
        request_id=row.request_id,
        account_number=row.account_number,
        type=TransactionType(row.type),
        amount=row.amount,
        counterparty_account=row.counterparty_account,
        decline_reason=row.decline_reason,
        ts=row.ts,
        applied_rate_id=row.applied_rate_id,
    )


class PostgresTransactionRepository(PostgresRepository):
    async def insert(
        self,
        *,
        request_id: UUID,
        account_number: str,
        type: str,
        amount: int,
        counterparty_account: str,
        decline_reason: Optional[str],
        ts: datetime,
        applied_rate_id: Optional[UUID] = None,
    ) -> None:
        statement = (
            pg_insert(TransactionORM)
            .values(
                request_id=request_id,
                account_number=account_number,
                type=type,
                amount=amount,
                counterparty_account=counterparty_account,
                decline_reason=decline_reason,
                ts=ts,
                applied_rate_id=applied_rate_id,
            )
            .on_conflict_do_nothing(
                index_elements=["request_id", "account_number", "type"]
            )
        )
        await self._session.execute(statement)
        await self._session.flush()

    async def list_by_account(
        self,
        account_number: str,
        *,
        limit: int,
        before: Optional[Tuple[datetime, UUID]] = None,
    ) -> List[Transaction]:
        from sqlalchemy import and_, or_, select

        conditions = [TransactionORM.account_number == account_number]
        if before is not None:
            before_ts, before_id = before
            conditions.append(
                or_(
                    TransactionORM.ts < before_ts,
                    and_(TransactionORM.ts == before_ts, TransactionORM.id < before_id),
                )
            )
        rows = await self._session.execute(
            select(TransactionORM)
            .where(and_(*conditions))
            .order_by(TransactionORM.ts.desc(), TransactionORM.id.desc())
            .limit(limit)
        )
        return [_to_domain(r) for r in rows.scalars().all()]


class PostgresTransactionWriter:
    """The write side `TransactionConsumer` is handed (spec §3.1).

    Deliberately NOT a `PostgresRepository`: consumer calls arrive off a Kafka
    thread, not an HTTP request, so there is no request-scoped session to
    share (see `_base.py`'s Unit-of-Work docs). Opens and commits its own
    session per call instead — the same split `PostgresAccountBalanceProjection`
    makes for the same reason.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def insert(
        self,
        *,
        request_id: UUID,
        account_number: str,
        type: str,
        amount: int,
        counterparty_account: str,
        decline_reason: Optional[str],
        ts: datetime,
        applied_rate_id: Optional[UUID] = None,
    ) -> None:
        statement = (
            pg_insert(TransactionORM)
            .values(
                request_id=request_id,
                account_number=account_number,
                type=type,
                amount=amount,
                counterparty_account=counterparty_account,
                decline_reason=decline_reason,
                ts=ts,
                applied_rate_id=applied_rate_id,
            )
            .on_conflict_do_nothing(
                index_elements=["request_id", "account_number", "type"]
            )
        )
        async with self._sessionmaker.begin() as session:
            await session.execute(statement)
