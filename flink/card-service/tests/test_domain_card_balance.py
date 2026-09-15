"""RED for Flink card-balance emission (task 3.1)."""
from __future__ import annotations

from datetime import datetime, timezone

import card_domain as domain

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


def _state(used_credit=0, processed=frozenset()):
    return domain.CardState(used_credit=used_credit, processed=processed)


def _purchase_event(**overrides):
    base = {
        "type": "purchase_requested",
        "request_id": "req-1",
        "card_id": "card-1",
        "card_account_id": "acct-1",
        "amount_usd": 30000,
        "credit_limit": 100000,
        "installments": 1,
    }
    base.update(overrides)
    return base


def _payment_event(**overrides):
    base = {
        "type": "card_payment_received",
        "request_id": "pay-1",
        "card_id": "card-1",
        "card_account_id": "acct-1",
        "amount_usd": 10000,
    }
    base.update(overrides)
    return base


def test_approval_and_payment_emit():
    decision = domain.decide(_state(0), _purchase_event(amount_usd=30000), NOW)
    assert hasattr(decision, "card_balance_events")
    assert len(decision.card_balance_events) == 1
    assert decision.card_balance_events[0]["card_account_id"] == "acct-1"
    assert decision.card_balance_events[0]["used_credit"] == 30000

    decision2 = domain.decide(_state(30000), _payment_event(amount_usd=10000), NOW)
    assert len(decision2.card_balance_events) == 1
    assert decision2.card_balance_events[0]["used_credit"] == 20000


def test_decline_and_dedup_emit_nothing():
    # decline: amount exceeds limit
    decision = domain.decide(_state(90000), _purchase_event(amount_usd=20000, credit_limit=100000), NOW)
    assert decision.new_used_credit is None
    assert getattr(decision, "card_balance_events", ()) == () or len(decision.card_balance_events) == 0

    # dedup: processed request
    decision2 = domain.decide(_state(0, processed=frozenset({"req-1"})), _purchase_event(), NOW)
    assert decision2 == domain.Decision.noop()
    assert getattr(decision2, "card_balance_events", ()) == () or len(decision2.card_balance_events) == 0


def test_overpayment_emits_negative():
    decision = domain.decide(_state(10000), _payment_event(amount_usd=20000), NOW)
    assert decision.card_balance_events[0]["used_credit"] == -10000
    assert decision.new_used_credit == -10000
