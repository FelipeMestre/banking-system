"""Postgres implementation of ILocationRepository."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ....domain.model import Location
from ..interfaces.common import Page
from ..schemas.models import LocationORM
from ._base import PostgresRepository, page_of


def _to_domain(row: LocationORM) -> Location:
    return Location(
        id=row.id,
        name=row.name,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresLocationRepository(PostgresRepository):
    async def create(self, *, name: str) -> Location:
        return _to_domain(await self._insert(LocationORM, {"name": name}))

    async def get(self, location_id: UUID) -> Optional[Location]:
        row = await self._fetch_one(LocationORM, LocationORM.id == location_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(LocationORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self, location_id: UUID, *, name: Optional[str] = None, active: Optional[bool] = None
    ) -> Optional[Location]:
        row = await self._update(
            LocationORM, LocationORM.id == location_id, {"name": name, "active": active}
        )
        return _to_domain(row) if row else None

    async def deactivate(self, location_id: UUID) -> Optional[Location]:
        # Soft delete: branches reference this row, so it must survive.
        row = await self._update(LocationORM, LocationORM.id == location_id, {"active": False})
        return _to_domain(row) if row else None
