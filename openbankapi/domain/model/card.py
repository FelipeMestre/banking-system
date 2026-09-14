"""A physical/virtual card: the credential belonging to a `CardAccount`."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Dict, FrozenSet
from uuid import UUID

CARD_NUMBER_PATTERN = re.compile(r"^[0-9]{16}$")
CARD_NUMBER_LENGTH = 16

# Expiration is issuance/renewal date plus this many years (spec: Card number
# generation requirement).
CARD_VALIDITY_YEARS = 4


def is_valid_card_number(value: str) -> bool:
    return bool(CARD_NUMBER_PATTERN.match(value))


class CardStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    REPLACED = "replaced"
    EXPIRED = "expired"


CARD_TRANSITIONS: Dict[CardStatus, FrozenSet[CardStatus]] = {
    CardStatus.ACTIVE: frozenset({CardStatus.BLOCKED, CardStatus.REPLACED, CardStatus.EXPIRED}),
    CardStatus.BLOCKED: frozenset({CardStatus.ACTIVE, CardStatus.REPLACED, CardStatus.EXPIRED}),
    CardStatus.REPLACED: frozenset(),
    CardStatus.EXPIRED: frozenset(),
}


@dataclass(frozen=True)
class Card:
    id: UUID
    card_account_id: UUID
    card_number: str
    expiration_date: date
    status: CardStatus
    created_at: datetime
    updated_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status is CardStatus.ACTIVE
