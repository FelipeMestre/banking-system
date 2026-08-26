"""Postgres implementation of IBranchRepository."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ....domain.model import Branch
from ..interfaces.common import Page
from ..models import BranchORM
from ._base import PostgresRepository, page_of


def _to_domain(row: BranchORM) -> Branch:
    return Branch(
        id=row.id,
        code=row.code,
        name=row.name,
        location_id=row.location_id,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresBranchRepository(PostgresRepository):
    async def create(self, *, code: str, name: str, location_id: UUID) -> Branch:
        # A bogus location_id trips the FK and comes back as
        # ReferencedEntityNotFoundError, which the controller turns into a 422
        # rather than leaking a driver error (spec §11.4).
        row = await self._insert(
            BranchORM, {"code": code, "name": name, "location_id": location_id}
        )
        return _to_domain(row)

    async def get(self, branch_id: UUID) -> Optional[Branch]:
        row = await self._fetch_one(BranchORM, BranchORM.id == branch_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(BranchORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self,
        branch_id: UUID,
        *,
        code: Optional[str] = None,
        name: Optional[str] = None,
        location_id: Optional[UUID] = None,
        active: Optional[bool] = None,
    ) -> Optional[Branch]:
        row = await self._update(
            BranchORM,
            BranchORM.id == branch_id,
            {"code": code, "name": name, "location_id": location_id, "active": active},
        )
        return _to_domain(row) if row else None

    async def deactivate(self, branch_id: UUID) -> Optional[Branch]:
        # Soft delete: accounts reference this row, so it must survive.
        row = await self._update(
            BranchORM, BranchORM.id == branch_id, {"active": False}
        )
        return _to_domain(row) if row else None
