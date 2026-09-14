"""RED for Credit Cards Phase 1: `CardAccountService.issue_card_account()`
and `.renew_card()` (T17). Pure unit tests against in-memory fakes — no DB,
no HTTP, matching this repo's fakes-based unit-test convention.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

import pytest

from openbankapi.domain.exceptions import InvalidCardStatusError
from openbankapi.domain.model import CARD_VALIDITY_YEARS, Card, CardAccount, CardAccountStatus, CardStatus
from openbankapi.infra.database.interfaces.common import Page


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _FakeCardAccountRepository:
    def __init__(self):
        self.rows: Dict[UUID, CardAccount] = {}
        self.create_calls = 0

    async def create(self, *, customer_id, paying_account_id, credit_limit) -> CardAccount:
        self.create_calls += 1
        entity = CardAccount(
            id=uuid.uuid4(), customer_id=customer_id, paying_account_id=paying_account_id,
            credit_limit=credit_limit, status=CardAccountStatus.ACTIVE,
            created_at=_now(), updated_at=_now(),
        )
        self.rows[entity.id] = entity
        return entity

    async def get_by_id(self, card_account_id: UUID) -> Optional[CardAccount]:
        return self.rows.get(card_account_id)

    async def list_by_customer(self, customer_id, *, limit, offset) -> Page:
        raise NotImplementedError

    async def update_status(self, card_account_id, *, status) -> Optional[CardAccount]:
        raise NotImplementedError

    async def update_limit(self, card_account_id, *, credit_limit) -> Optional[CardAccount]:
        raise NotImplementedError


class _FakeCardRepository:
    def __init__(self):
        self.rows: Dict[UUID, Card] = {}
        self.by_number: Dict[str, UUID] = {}
        self.create_calls = 0
        self._next_number = 1000000000000001

    async def create(self, *, card_account_id, expiration_date) -> Card:
        self.create_calls += 1
        number = str(self._next_number)
        self._next_number += 1
        entity = Card(
            id=uuid.uuid4(), card_account_id=card_account_id, card_number=number,
            expiration_date=expiration_date, status=CardStatus.ACTIVE,
            created_at=_now(), updated_at=_now(),
        )
        self.rows[entity.id] = entity
        self.by_number[number] = entity.id
        return entity

    async def get_by_number(self, card_number: str) -> Optional[Card]:
        card_id = self.by_number.get(card_number)
        return self.rows.get(card_id) if card_id else None

    async def get_active_for_account(self, card_account_id: UUID) -> Optional[Card]:
        return next(
            (c for c in self.rows.values() if c.card_account_id == card_account_id and c.is_active),
            None,
        )

    async def mark_replaced(self, card_id: UUID) -> Optional[Card]:
        current = self.rows.get(card_id)
        if current is None:
            return None
        updated = Card(
            id=current.id, card_account_id=current.card_account_id,
            card_number=current.card_number, expiration_date=current.expiration_date,
            status=CardStatus.REPLACED, created_at=current.created_at, updated_at=_now(),
        )
        self.rows[card_id] = updated
        return updated

    async def update_status(self, card_id: UUID, *, status) -> Optional[Card]:
        raise NotImplementedError


def test_issue_card_account_creates_account_and_card_atomically():
    from openbankapi.domain.service.card_account_service import CardAccountService

    card_accounts, cards = _FakeCardAccountRepository(), _FakeCardRepository()
    service = CardAccountService(card_accounts, cards)
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()

    account, card = asyncio.run(
        service.issue_card_account(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=Decimal("1500")
        )
    )

    assert card_accounts.create_calls == 1
    assert cards.create_calls == 1
    assert card.card_account_id == account.id
    assert account.status is CardAccountStatus.ACTIVE
    assert card.status is CardStatus.ACTIVE
    assert card.expiration_date.year == date.today().year + CARD_VALIDITY_YEARS


def test_renew_card_preserves_account_identity_and_credit_limit():
    from openbankapi.domain.service.card_account_service import CardAccountService

    card_accounts, cards = _FakeCardAccountRepository(), _FakeCardRepository()
    service = CardAccountService(card_accounts, cards)
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
    account, old_card = asyncio.run(
        service.issue_card_account(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=Decimal("1500")
        )
    )

    new_card = asyncio.run(service.renew_card(account.id))

    assert new_card.card_account_id == account.id
    assert new_card.card_number != old_card.card_number
    assert cards.rows[old_card.id].status is CardStatus.REPLACED
    refreshed_account = asyncio.run(card_accounts.get_by_id(account.id))
    assert refreshed_account.credit_limit == account.credit_limit


def test_renew_card_raises_when_account_is_not_active():
    from openbankapi.domain.service.card_account_service import CardAccountService

    card_accounts, cards = _FakeCardAccountRepository(), _FakeCardRepository()
    service = CardAccountService(card_accounts, cards)
    account, _ = asyncio.run(
        service.issue_card_account(
            customer_id=uuid.uuid4(), paying_account_id=uuid.uuid4(), credit_limit=Decimal("1500")
        )
    )
    blocked = CardAccount(
        id=account.id, customer_id=account.customer_id, paying_account_id=account.paying_account_id,
        credit_limit=account.credit_limit, status=CardAccountStatus.BLOCKED,
        created_at=account.created_at, updated_at=account.updated_at,
    )
    card_accounts.rows[account.id] = blocked

    with pytest.raises(InvalidCardStatusError):
        asyncio.run(service.renew_card(account.id))
