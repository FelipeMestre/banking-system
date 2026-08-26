"""A branch: many per `locacion`, and the branch a `cuenta` is opened at (§3.3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Sucursal:
    id: UUID
    codigo: str
    nombre: str
    locacion_id: UUID
    activa: bool
    created_at: datetime
    updated_at: datetime

    @property
    def is_open(self) -> bool:
        return self.activa
