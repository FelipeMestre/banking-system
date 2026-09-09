"""RED for Credit Cards Phase 1: `CardAccount`/`Card` dataclasses + transition maps (T7)."""
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

import pytest

from openbankapi.domain.model.card import (
    CARD_TRANSITIONS,
    CARD_VALIDITY_YEARS,
    Card,
    CardStatus,
)
from openbankapi.domain.model.card_account import (
    CARD_ACCOUNT_TRANSITIONS,
    CardAccount,
    CardAccountStatus,
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _card_account() -> CardAccount:
    return CardAccount(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        paying_account_id=uuid.uuid4(),
        credit_limit=1000,
        status=CardAccountStatus.ACTIVE,
        created_at=_now(),
        updated_at=_now(),
    )


def _card() -> Card:
    return Card(
        id=uuid.uuid4(),
        card_account_id=uuid.uuid4(),
        card_number="1234567812345678",
        expiration_date=dt.date.today(),
        status=CardStatus.ACTIVE,
        created_at=_now(),
        updated_at=_now(),
    )


def test_card_account_is_frozen():
    account = _card_account()
    with pytest.raises(dataclasses.FrozenInstanceError):
        account.credit_limit = 2000  # type: ignore[misc]


def test_card_is_frozen():
    card = _card()
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.status = CardStatus.BLOCKED  # type: ignore[misc]


def test_card_account_status_is_str_enum():
    assert CardAccountStatus.ACTIVE == "active"
    assert isinstance(CardAccountStatus.ACTIVE, str)


def test_card_status_is_str_enum():
    assert CardStatus.ACTIVE == "active"
    assert isinstance(CardStatus.ACTIVE, str)


def test_card_account_transitions_allow_active_to_blocked():
    assert CardAccountStatus.BLOCKED in CARD_ACCOUNT_TRANSITIONS[CardAccountStatus.ACTIVE]


def test_card_account_transitions_reject_closed_to_active():
    assert CardAccountStatus.ACTIVE not in CARD_ACCOUNT_TRANSITIONS[CardAccountStatus.CLOSED]


def test_card_transitions_allow_active_to_blocked():
    assert CardStatus.BLOCKED in CARD_TRANSITIONS[CardStatus.ACTIVE]


def test_card_transitions_reject_replaced_to_active():
    assert CardStatus.ACTIVE not in CARD_TRANSITIONS[CardStatus.REPLACED]


def test_card_validity_years_is_four():
    assert CARD_VALIDITY_YEARS == 4
