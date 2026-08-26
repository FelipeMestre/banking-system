"""A branch: many per `location`, and the branch a `account` is opened at (§3.3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Branch:
    id: UUID
    code: str
    name: str
    location_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def is_open(self) -> bool:
        return self.active
