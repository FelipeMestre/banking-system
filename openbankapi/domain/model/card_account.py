"""A card account: the parent aggregate for a customer's credit-card line."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, FrozenSet, Union
from uuid import UUID


class CardAccountStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    CLOSED = "closed"


# Table-driven transition map: the smallest change surface when a new
# transition needs adding later, and usable outside HTTP (design decision).
CARD_ACCOUNT_TRANSITIONS: Dict[CardAccountStatus, FrozenSet[CardAccountStatus]] = {
    CardAccountStatus.ACTIVE: frozenset({CardAccountStatus.BLOCKED, CardAccountStatus.CLOSED}),
    CardAccountStatus.BLOCKED: frozenset({CardAccountStatus.ACTIVE, CardAccountStatus.CLOSED}),
    CardAccountStatus.CLOSED: frozenset(),
}


@dataclass(frozen=True)
class CardAccount:
    id: UUID
    customer_id: UUID
    paying_account_id: UUID
    credit_limit: Union[int, Decimal]
    status: CardAccountStatus
    created_at: datetime
    updated_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status is CardAccountStatus.ACTIVE
