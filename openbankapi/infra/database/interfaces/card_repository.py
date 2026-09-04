"""Contract for `cards` persistence.

`typing.Protocol`, not `abc.ABC` — same convention as `ICardAccountRepository`.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from ....domain.model import Card
from .common import Page


@runtime_checkable
class ICardRepository(Protocol):
    async def create(self, *, card_account_id: UUID, expiration_date: date) -> Card:
        """Create a card with a server-generated `card_number`.

        The number is retried internally on a UNIQUE collision (spec: Card
        number generation requirement) and never surfaces a 500 for that
        reason.
        """
        ...

    async def get_by_number(self, card_number: str) -> Optional[Card]: ...

    async def list_all(self, *, limit: int, offset: int) -> Page[Card]:
        """All cards across every customer — admin-only listing (e.g. to pick a
        card for a simulated purchase), never customer-scoped like the rest of
        this interface."""
        ...

    async def get_active_for_account(self, card_account_id: UUID) -> Optional[Card]:
        """The single currently-`active` card for a card account, if any."""
        ...

    async def mark_replaced(self, card_id: UUID) -> Optional[Card]:
        """Transition a card to `replaced` — used during renewal."""
        ...

    async def update_status(self, card_id: UUID, *, status: str) -> Optional[Card]:
        """Set `status` unconditionally — the caller must validate the
        transition against `CARD_TRANSITIONS` before calling this."""
        ...
