"""A location: the geographic grouping a `sucursal` belongs to (spec §3.2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Locacion:
    id: UUID
    nombre: str
    created_at: datetime
    updated_at: datetime
