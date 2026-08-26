"""A customer (spec §3.4).

`fecha_nacimiento` and `genero` are personal data. `repr=False` plus the
hand-written `__repr__` below is why: a frozen dataclass's generated repr prints
every field, so a single `LOG.debug("%r", cliente)` anywhere in the codebase
would put a birth date in a log file. Redacting at the type makes that
impossible rather than merely discouraged.

`age` is computed, never stored: a stored age is wrong the day after it is
written (§3.4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID


@dataclass(frozen=True, repr=False)
class Cliente:
    id: UUID
    numero_identificacion: str
    nombre: str
    apellido: str
    fecha_nacimiento: date
    genero: Optional[str]
    activo: bool
    created_at: datetime
    updated_at: datetime

    def age_at(self, today: date) -> int:
        """Completed years as of `today`. Injected date keeps this testable."""
        had_birthday = (today.month, today.day) >= (
            self.fecha_nacimiento.month,
            self.fecha_nacimiento.day,
        )
        return today.year - self.fecha_nacimiento.year - (0 if had_birthday else 1)

    @property
    def age(self) -> int:
        """Age derived from `fecha_nacimiento` on every read (§3.4).

        There is no `age` column and there will not be one: a stored age is
        already wrong the day after it is written, and nothing in this system
        would be responsible for correcting it. Deriving it here means the only
        persisted fact is the one that never changes, and `ClienteResponseDTO`
        picks this property up through `from_attributes=True`.
        """
        return self.age_at(datetime.now(timezone.utc).date())

    def __repr__(self) -> str:
        return f"Cliente(id={self.id!s}, numero_identificacion={self.numero_identificacion!r})"
