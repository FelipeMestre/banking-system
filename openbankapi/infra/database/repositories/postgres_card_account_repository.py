"""Postgres implementation of `ICardAccountRepository` (Credit Cards Phase 1)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union
from uuid import UUID

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
