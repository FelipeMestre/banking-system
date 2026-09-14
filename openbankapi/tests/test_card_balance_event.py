"""RED for CardBalanceUpdated event shape (task 1.3)."""
from __future__ import annotations

import pytest

from openbankapi.domain.events.card_balance_updated import CardBalanceUpdated


def test_valid_and_negative_parse():
    event = CardBalanceUpdated.from_payload(
        {"card_account_id": "550e8400-e29b-41d4-a716-446655440000", "used_credit": 30000, "ts": "2026-01-01T00:00:00Z"}
    )
    assert event.used_credit == 30000
    assert event.card_account_id == "550e8400-e29b-41d4-a716-446655440000"

    negative = CardBalanceUpdated.from_payload(
        {"card_account_id": "550e8400-e29b-41d4-a716-446655440000", "used_credit": -5000, "ts": "2026-01-01T00:00:00Z"}
    )
    assert negative.used_credit == -5000


def test_negative_is_not_clamped():
    event = CardBalanceUpdated.from_payload(
        {"card_account_id": "550e8400-e29b-41d4-a716-446655440000", "used_credit": -10000, "ts": "t"}
    )
    assert event.used_credit == -10000


def test_malformed_rejected():
    with pytest.raises((ValueError, KeyError)):
        CardBalanceUpdated.from_payload({"card_account_id": 123, "used_credit": "lots", "ts": "t"})
    with pytest.raises((ValueError, KeyError)):
        CardBalanceUpdated.from_payload({"card_account_id": "550e8400-e29b-41d4-a716-446655440000", "ts": "t"})
    with pytest.raises((ValueError, KeyError)):
        CardBalanceUpdated.from_payload({"card_account_id": "550e8400-e29b-41d4-a716-446655440000", "used_credit": "lots"})


def test_missing_used_credit_raises():
    with pytest.raises((ValueError, KeyError)):
        CardBalanceUpdated.from_payload({"card_account_id": "abc"})
