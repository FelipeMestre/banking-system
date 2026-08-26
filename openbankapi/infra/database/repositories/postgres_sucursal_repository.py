"""Postgres implementation of ISucursalRepository."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ....domain.model import Sucursal
from ..interfaces.common import Page
from ..models import SucursalORM
from ._base import PostgresRepository, page_of


def _to_domain(row: SucursalORM) -> Sucursal:
    return Sucursal(
        id=row.id,
        codigo=row.codigo,
        nombre=row.nombre,
        locacion_id=row.locacion_id,
        activa=row.activa,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresSucursalRepository(PostgresRepository):
    async def create(self, *, codigo: str, nombre: str, locacion_id: UUID) -> Sucursal:
        # A bogus locacion_id trips the FK and comes back as
        # ReferencedEntityNotFoundError, which the controller turns into a 422
        # rather than leaking a driver error (spec §11.4).
        row = await self._insert(
            SucursalORM, {"codigo": codigo, "nombre": nombre, "locacion_id": locacion_id}
        )
        return _to_domain(row)

    async def get(self, sucursal_id: UUID) -> Optional[Sucursal]:
        row = await self._fetch_one(SucursalORM, SucursalORM.id == sucursal_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(SucursalORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self,
        sucursal_id: UUID,
        *,
        codigo: Optional[str] = None,
        nombre: Optional[str] = None,
        locacion_id: Optional[UUID] = None,
        activa: Optional[bool] = None,
    ) -> Optional[Sucursal]:
        row = await self._update(
            SucursalORM,
            SucursalORM.id == sucursal_id,
            {"codigo": codigo, "nombre": nombre, "locacion_id": locacion_id, "activa": activa},
        )
        return _to_domain(row) if row else None

    async def deactivate(self, sucursal_id: UUID) -> Optional[Sucursal]:
        # Soft delete: accounts reference this row, so it must survive.
        row = await self._update(
            SucursalORM, SucursalORM.id == sucursal_id, {"activa": False}
        )
        return _to_domain(row) if row else None
