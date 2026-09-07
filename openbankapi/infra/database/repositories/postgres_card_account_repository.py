"""Postgres implementation of `ICardAccountRepository` (Credit Cards Phase 1)."""
from __future__ import annotations

import datetime as dt
from datetime import date
from decimal import Decimal
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..interfaces.common import Page
from ..schemas.models import CardAccountORM
from ._base import PostgresRepository, page_of
from ....domain.model import CardAccount, CardAccountStatus


def _to_domain(row: CardAccountORM) -> CardAccount:
    return CardAccount(
        id=row.id,
        customer_id=row.customer_id,
        paying_account_id=row.paying_account_id,
        credit_limit=row.credit_limit,
        status=CardAccountStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        used_credit=row.used_credit,
    )


class PostgresCardAccountRepository(PostgresRepository):
    _UPDATABLE = frozenset({"credit_limit", "status"})

    async def create(
        self, *, customer_id: UUID, paying_account_id: UUID, credit_limit: Union[int, Decimal]
    ) -> CardAccount:
        row = await self._insert(
            CardAccountORM,
            {
                "customer_id": customer_id,
                "paying_account_id": paying_account_id,
                "credit_limit": credit_limit,
            },
        )
        return _to_domain(row)

    async def get_by_id(self, card_account_id: UUID) -> Optional[CardAccount]:
        row = await self._fetch_one(CardAccountORM, CardAccountORM.id == card_account_id)
        return _to_domain(row) if row else None

    async def list_by_customer(
        self, customer_id: UUID, *, limit: int, offset: int
    ) -> Page[CardAccount]:
        rows, total = await self._fetch_page(
            CardAccountORM, CardAccountORM.customer_id == customer_id, limit=limit, offset=offset
        )
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update_status(self, card_account_id: UUID, *, status: str) -> Optional[CardAccount]:
        row = await self._update(
            CardAccountORM, CardAccountORM.id == card_account_id, {"status": status}
        )
        return _to_domain(row) if row else None

    async def update_limit(
        self, card_account_id: UUID, *, credit_limit: Union[int, Decimal]
    ) -> Optional[CardAccount]:
        row = await self._update(
            CardAccountORM, CardAccountORM.id == card_account_id, {"credit_limit": credit_limit}
        )
        return _to_domain(row) if row else None

    async def list_active_ids(self) -> List[UUID]:
        """Every card_account still billable — everything except CLOSED
        (Credit Cards Phase 4 correction: a BLOCKED account still has an
        outstanding balance and must keep getting statements; blocking only
        affects Phase 2's purchase check, not this phase)."""
        result = await self._session.execute(
            select(CardAccountORM.id).where(
                CardAccountORM.status != CardAccountStatus.CLOSED.value
            )
        )
        return list(result.scalars().all())

    async def get_issuance_date(self, card_account_id: UUID) -> date:
        row = await self._fetch_one(CardAccountORM, CardAccountORM.id == card_account_id)
        return row.created_at.date()


class PostgresCardBalanceProjection:
    """The only writer of `card_accounts.used_credit`.

    Deliberately NOT a `PostgresRepository`: that base class expects an
    already-open, request-scoped `AsyncSession` handed out by
    `infra/database/session.get_db_session` — but this class is driven by the
    `card-balances` Kafka consumer thread, not an HTTP request, so there is no
    request to scope a session to. It keeps its own `sessionmaker` and opens
    one session per call instead. Constructed once in `main.py` and handed
    only to that consumer — nothing that serves an HTTP request may ever hold one.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def apply_used_credit(self, card_account_id: UUID, used_credit: int) -> bool:
        async with self._sessionmaker.begin() as session:
            result = await session.execute(
                sql_update(CardAccountORM)
                .where(CardAccountORM.id == card_account_id)
                .values(used_credit=used_credit, updated_at=dt.datetime.now(dt.timezone.utc))
            )
            return bool(result.rowcount)

    async def read_used_credit(self, card_account_id: UUID) -> Optional[int]:
        """Only used by tests and diagnostics."""
        async with self._sessionmaker() as session:
            return await session.scalar(
                select(CardAccountORM.used_credit).where(CardAccountORM.id == card_account_id)
            )
