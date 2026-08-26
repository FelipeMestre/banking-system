"""Contract for `locaciones` persistence (spec §8.2 — no delete)."""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Locacion
from .common import Page


class ILocacionRepository(Protocol):
    async def create(self, *, nombre: str) -> Locacion: ...

    async def get(self, locacion_id: UUID) -> Optional[Locacion]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Locacion]: ...

    async def update(self, locacion_id: UUID, *, nombre: Optional[str]) -> Optional[Locacion]: ...
