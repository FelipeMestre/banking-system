"""A customer (spec §3.4).

`date_of_birth` and `gender` are personal data. `repr=False` plus the
hand-written `__repr__` below is why: a frozen dataclass's generated repr prints
every field, so a single `LOG.debug("%r", customer)` anywhere in the codebase
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
class Customer:
    id: UUID
    identification_number: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Optional[str]
    active: bool
    created_at: datetime
    updated_at: datetime
    # Set only via PATCH /customers/{id}/auth0-link (spec §1.1). Never inferred.
    auth0_sub: Optional[str] = None

    def age_at(self, today: date) -> int:
        """Completed years as of `today`. Injected date keeps this testable."""
        had_birthday = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return today.year - self.date_of_birth.year - (0 if had_birthday else 1)

    @property
    def age(self) -> int:
        """Age derived from `date_of_birth` on every read (§3.4).

        There is no `age` column and there will not be one: a stored age is
        already wrong the day after it is written, and nothing in this system
        would be responsible for correcting it. Deriving it here means the only
        persisted fact is the one that never changes, and `CustomerResponseDTO`
        picks this property up through `from_attributes=True`.
        """
        return self.age_at(datetime.now(timezone.utc).date())

    def __repr__(self) -> str:
        return f"Customer(id={self.id!s}, identification_number={self.identification_number!r})"
