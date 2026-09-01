"""Postgres implementation of ICustomerRepository.

Nothing here logs `date_of_birth` or `gender` (spec §3.4), and the domain
entity's redacted `__repr__` means an accidental `%r` cannot either.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from ....domain.model import Customer
from ..interfaces.common import Page
from ..schemas.models import CustomerORM
from ._base import PostgresRepository, page_of


def _to_domain(row: CustomerORM) -> Customer:
    return Customer(
        id=row.id,
        identification_number=row.identification_number,
        first_name=row.first_name,
        last_name=row.last_name,
        date_of_birth=row.date_of_birth,
        gender=row.gender,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        auth0_sub=row.auth0_sub,
    )


class PostgresCustomerRepository(PostgresRepository):
    async def create(
        self,
        *,
        identification_number: str,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        gender: Optional[str],
    ) -> Customer:
        row = await self._insert(
            CustomerORM,
            {
                "identification_number": identification_number,
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date_of_birth,
                "gender": gender,
            },
        )
        return _to_domain(row)

    async def get(self, customer_id: UUID) -> Optional[Customer]:
        row = await self._fetch_one(CustomerORM, CustomerORM.id == customer_id)
        return _to_domain(row) if row else None

    async def get_by_auth0_sub(self, sub: str) -> Optional[Customer]:
        row = await self._fetch_one(CustomerORM, CustomerORM.auth0_sub == sub)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(CustomerORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self,
        customer_id: UUID,
        *,
        identification_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        gender: Optional[str] = None,
        active: Optional[bool] = None,
        auth0_sub: Optional[str] = None,
    ) -> Optional[Customer]:
        row = await self._update(
            CustomerORM,
            CustomerORM.id == customer_id,
            {
                "identification_number": identification_number,
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date_of_birth,
                "gender": gender,
                "active": active,
                "auth0_sub": auth0_sub,
            },
        )
        return _to_domain(row) if row else None

    async def deactivate(self, customer_id: UUID) -> Optional[Customer]:
        row = await self._update(CustomerORM, CustomerORM.id == customer_id, {"active": False})
        return _to_domain(row) if row else None