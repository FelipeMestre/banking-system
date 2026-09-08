"""Postgres implementation of `ICardAccountRepository` (Credit Cards Phase 1)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import select

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
    )


class PostgresCardAccountRepository(PostgresRepository):
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
        self, customer_id: UUID, *, limit: int, offset: int, status: Optional[str] = None
    ) -> Page[CardAccount]:
        conditions = [CardAccountORM.customer_id == customer_id]
        if status is not None:
            conditions.append(CardAccountORM.status == status)
        rows, total = await self._fetch_page(CardAccountORM, *conditions, limit=limit, offset=offset)
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
