"""Contract for `locations` persistence (spec §8.2 — soft delete)."""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Location
from .common import Page


class ILocationRepository(Protocol):
    async def create(self, *, name: str) -> Location: ...

    async def get(self, location_id: UUID) -> Optional[Location]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Location]: ...

    async def update(
        self, location_id: UUID, *, name: Optional[str] = None, active: Optional[bool] = None
    ) -> Optional[Location]: ...

    async def deactivate(self, location_id: UUID) -> Optional[Location]:
        """Soft delete: `active = false`. The row stays — branches reference it."""
        ...
