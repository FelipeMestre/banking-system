"""Issue/renew orchestration (Credit Cards Phase 1).

Plain domain object: no FastAPI, no Depends, no import from `api`. These are
the ONLY two operations this phase needs a service for — everything else
(`get`/`list`/`update-limit`/`block`/`unblock`) is a single-repository call
and stays router -> repository directly (AGENTS.md's 1-2-repo rule).

Both repositories are constructed from the same request-scoped `DbSession` by
the DI wiring in `config/dependencies.py`; each repository method only
`flush()`s (see `_base.py`'s Unit-of-Work docstring), so if the second insert
in `issue_card_account` fails, the whole request rolls back — neither row
survives (design's Transaction Boundary section).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Tuple, Union
from uuid import UUID

from ..exceptions import CardAccountNotFoundError, CardNotFoundError, InvalidCardStatusError
from ..model import CARD_VALIDITY_YEARS, Card, CardAccount, CardAccountStatus
from ...infra.database.interfaces import ICardAccountRepository, ICardRepository


def _expiration_from(today: date) -> date:
    """`today` plus `CARD_VALIDITY_YEARS`, handling the Feb-29 edge case the
    same way `date.replace` naturally forces it: falling back to Feb 28."""
    try:
        return today.replace(year=today.year + CARD_VALIDITY_YEARS)
    except ValueError:
        return today + timedelta(days=365 * CARD_VALIDITY_YEARS)


class CardAccountService:
    def __init__(self, card_account_repository: ICardAccountRepository, card_repository: ICardRepository):
        self._card_accounts = card_account_repository
        self._cards = card_repository

    async def issue_card_account(
        self, *, customer_id: UUID, paying_account_id: UUID, credit_limit: Union[int, Decimal]
    ) -> Tuple[CardAccount, Card]:
        """Create an active `CardAccount` and its first active `Card` together.

        Neither repository call commits (Unit-of-Work): if the card insert
        fails, the account insert rolls back with it when the request's
        shared session is torn down.
        """
        card_account = await self._card_accounts.create(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=credit_limit
        )
        card = await self._cards.create(
            card_account_id=card_account.id, expiration_date=_expiration_from(date.today())
        )
        return card_account, card

    async def renew_card(self, card_account_id: UUID) -> Card:
        """Replace the account's active card with a fresh one.

        `card_account_id` and `credit_limit` are unchanged by construction —
        renewal only ever touches `cards`, never `card_accounts` (spec:
        "Renewal preserves account identity").
        """
        card_account = await self._card_accounts.get_by_id(card_account_id)
        if card_account is None:
            raise CardAccountNotFoundError(card_account_id)
        if card_account.status is not CardAccountStatus.ACTIVE:
            raise InvalidCardStatusError(card_account.status.value, "renew")

        old_card = await self._cards.get_active_for_account(card_account_id)
        if old_card is None:
            raise CardNotFoundError(card_account_id)

        await self._cards.mark_replaced(old_card.id)
        return await self._cards.create(
            card_account_id=card_account_id, expiration_date=_expiration_from(date.today())
        )
