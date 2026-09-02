"""Contract for `branches` persistence (spec §8.2 — soft delete)."""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Branch
from .common import Page


class IBranchRepository(Protocol):
    async def create(self, *, code: str, name: str, location_id: UUID) -> Branch: ...

    async def get(self, branch_id: UUID) -> Optional[Branch]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Branch]: ...

    async def update(
        self,
        branch_id: UUID,
        *,
        code: Optional[str] = None,
        name: Optional[str] = None,
        location_id: Optional[UUID] = None,
        active: Optional[bool] = None,
    ) -> Optional[Branch]: ...

    async def deactivate(self, branch_id: UUID) -> Optional[Branch]:
        """Soft delete: `active = false`. The row stays; accounts reference it."""
        ...

    async def get_oldest_active(self) -> Optional[Branch]:
        """The ACTIVE branch with the earliest creation order.

        Resolves the default branch for `POST /accounts/me` with no
        hardcoded or configured branch id: earliest `created_at`, tied
        broken by lowest `id`.
        """
        ...
