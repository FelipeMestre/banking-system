"""Contract for `sucursales` persistence (spec §8.2 — soft delete)."""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Sucursal
from .common import Page


class ISucursalRepository(Protocol):
    async def create(self, *, codigo: str, nombre: str, locacion_id: UUID) -> Sucursal: ...

    async def get(self, sucursal_id: UUID) -> Optional[Sucursal]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Sucursal]: ...

    async def update(
        self,
        sucursal_id: UUID,
        *,
        codigo: Optional[str] = None,
        nombre: Optional[str] = None,
        locacion_id: Optional[UUID] = None,
        activa: Optional[bool] = None,
    ) -> Optional[Sucursal]: ...

    async def deactivate(self, sucursal_id: UUID) -> Optional[Sucursal]:
        """Soft delete: `activa = false`. The row stays; accounts reference it."""
        ...
