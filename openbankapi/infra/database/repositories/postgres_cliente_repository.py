"""Postgres implementation of IClienteRepository.

Nothing here logs `fecha_nacimiento` or `genero` (spec §3.4), and the domain
entity's redacted `__repr__` means an accidental `%r` cannot either.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from ....domain.model import Cliente
from ..interfaces.common import Page
from ..models import ClienteORM
from ._base import PostgresRepository, page_of


def _to_domain(row: ClienteORM) -> Cliente:
    return Cliente(
        id=row.id,
        numero_identificacion=row.numero_identificacion,
        nombre=row.nombre,
        apellido=row.apellido,
        fecha_nacimiento=row.fecha_nacimiento,
        genero=row.genero,
        activo=row.activo,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresClienteRepository(PostgresRepository):
    async def create(
        self,
        *,
        numero_identificacion: str,
        nombre: str,
        apellido: str,
        fecha_nacimiento: date,
        genero: Optional[str],
    ) -> Cliente:
        row = await self._insert(
            ClienteORM,
            {
                "numero_identificacion": numero_identificacion,
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": fecha_nacimiento,
                "genero": genero,
            },
        )
        return _to_domain(row)

    async def get(self, cliente_id: UUID) -> Optional[Cliente]:
        row = await self._fetch_one(ClienteORM, ClienteORM.id == cliente_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(ClienteORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self,
        cliente_id: UUID,
        *,
        numero_identificacion: Optional[str] = None,
        nombre: Optional[str] = None,
        apellido: Optional[str] = None,
        fecha_nacimiento: Optional[date] = None,
        genero: Optional[str] = None,
        activo: Optional[bool] = None,
    ) -> Optional[Cliente]:
        row = await self._update(
            ClienteORM,
            ClienteORM.id == cliente_id,
            {
                "numero_identificacion": numero_identificacion,
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": fecha_nacimiento,
                "genero": genero,
                "activo": activo,
            },
        )
        return _to_domain(row) if row else None

    async def deactivate(self, cliente_id: UUID) -> Optional[Cliente]:
        row = await self._update(ClienteORM, ClienteORM.id == cliente_id, {"activo": False})
        return _to_domain(row) if row else None
