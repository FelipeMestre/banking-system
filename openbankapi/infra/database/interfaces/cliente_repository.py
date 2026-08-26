"""Contract for `clientes` persistence (spec §8.2 — soft delete)."""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Cliente
from .common import Page


class IClienteRepository(Protocol):
    async def create(
        self,
        *,
        numero_identificacion: str,
        nombre: str,
        apellido: str,
        fecha_nacimiento: date,
        genero: Optional[str],
    ) -> Cliente: ...

    async def get(self, cliente_id: UUID) -> Optional[Cliente]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Cliente]: ...

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
    ) -> Optional[Cliente]: ...

    async def deactivate(self, cliente_id: UUID) -> Optional[Cliente]: ...
