"""Postgres implementation of `ICardRepository` (Credit Cards Phase 1).

`generate_card_number()` + the SAVEPOINT-retry loop in `create()` mirror
`postgres_account_repository.py`'s own account-number generator verbatim —
same rationale, only the length constant and the target error type differ
(design decision: no shared generic generator, matches this codebase's
existing per-entity duplication).
"""
from __future__ import annotations

import logging
import secrets
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from ..errors import translate
from ..interfaces.common import Page
from ..schemas.models import CardORM
from ._base import PostgresRepository, page_of
from ....domain.exceptions import DuplicateCardNumberError
from ....domain.model import CARD_NUMBER_LENGTH, Card, CardStatus

LOG = logging.getLogger("openbankapi.cards")

# Same rationale as accounts: with 10^16 possibilities a single collision is
# already improbable; several in a row means the generator is broken, not luck.
_GENERATION_ATTEMPTS = 5


def generate_card_number() -> str:
    """16 random digits, leading zeros preserved — `secrets`, not `random`:
    this value is a publicly quoted card identifier."""
    return "".join(secrets.choice("0123456789") for _ in range(CARD_NUMBER_LENGTH))


def _to_domain(row: CardORM) -> Card:
    return Card(
        id=row.id,
        card_account_id=row.card_account_id,
        card_number=row.card_number,
        expiration_date=row.expiration_date,
        status=CardStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresCardRepository(PostgresRepository):
    async def create(self, *, card_account_id: UUID, expiration_date: date) -> Card:
        """Insert with a server-generated number, retrying on collision.

        Each attempt runs inside its own SAVEPOINT (`begin_nested`), not a new
        transaction, so a colliding attempt only undoes that one insert — it
        does not abort whatever else the shared request session has already
        done (verbatim structure of `PostgresAccountRepository.create()`).
        """
        last: Optional[DuplicateCardNumberError] = None
        for attempt in range(_GENERATION_ATTEMPTS):
            card_number = generate_card_number()
            values = {
                "card_account_id": card_account_id,
                "card_number": card_number,
                "expiration_date": expiration_date,
            }
            try:
                async with self._session.begin_nested():
                    row = CardORM(**values)
                    self._session.add(row)
                    await self._session.flush()
                await self._session.refresh(row)
                return _to_domain(row)
            except IntegrityError as error:
                translated = translate(error, values=values)
                if not isinstance(translated, DuplicateCardNumberError):
                    raise translated from error
                last = translated
                LOG.warning("card_number collision on attempt %d; retrying", attempt + 1)
        raise last if last else RuntimeError("card creation failed without a cause")

    async def get_by_number(self, card_number: str) -> Optional[Card]:
        row = await self._fetch_one(CardORM, CardORM.card_number == card_number)
        return _to_domain(row) if row else None

    async def list_all(self, *, limit: int, offset: int) -> Page[Card]:
        rows, total = await self._fetch_page(CardORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def get_active_for_account(self, card_account_id: UUID) -> Optional[Card]:
        row = await self._fetch_one(
            CardORM,
            CardORM.card_account_id == card_account_id,
            CardORM.status == CardStatus.ACTIVE.value,
        )
        return _to_domain(row) if row else None

    async def mark_replaced(self, card_id: UUID) -> Optional[Card]:
        row = await self._update(
            CardORM, CardORM.id == card_id, {"status": CardStatus.REPLACED.value}
        )
        return _to_domain(row) if row else None

    async def update_status(self, card_id: UUID, *, status: str) -> Optional[Card]:
        row = await self._update(CardORM, CardORM.id == card_id, {"status": status})
        return _to_domain(row) if row else None
