"""Contract for `customers` persistence (spec §8.2 — soft delete)."""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Customer
from .common import Page


class ICustomerRepository(Protocol):
    async def create(
        self,
        *,
        identification_number: str,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        gender: Optional[str],
    ) -> Customer: ...

    async def get(self, customer_id: UUID) -> Optional[Customer]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Customer]: ...

    async def update(
        self,
        customer_id: UUID,
        *,
        identification_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        gender: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> Optional[Customer]: ...

    async def deactivate(self, customer_id: UUID) -> Optional[Customer]: ...
