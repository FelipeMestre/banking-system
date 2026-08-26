"""Postgres implementation of ILocacionRepository."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ....domain.model import Locacion
from ..interfaces.common import Page
from ..models import LocacionORM
from ._base import PostgresRepository, page_of


def _to_domain(row: LocacionORM) -> Locacion:
    return Locacion(
        id=row.id,
        nombre=row.nombre,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresLocacionRepository(PostgresRepository):
    async def create(self, *, nombre: str) -> Locacion:
        return _to_domain(await self._insert(LocacionORM, {"nombre": nombre}))

    async def get(self, locacion_id: UUID) -> Optional[Locacion]:
        row = await self._fetch_one(LocacionORM, LocacionORM.id == locacion_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(LocacionORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(self, locacion_id: UUID, *, nombre: Optional[str]) -> Optional[Locacion]:
        row = await self._update(LocacionORM, LocacionORM.id == locacion_id, {"nombre": nombre})
        return _to_domain(row) if row else None
