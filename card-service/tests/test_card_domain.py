"""RED for the Card Service's pure `decide()` (task 2.2).

Mirrors `account-service/tests/test_domain.py`'s style: pure function, no
Flink runtime, no Postgres. All amounts are integer cents, `credit_limit`
and `amount_usd` arrive on the event itself and are NEVER read from
`CardState` — the single most important design point of this phase.
"""
from __future__ import annotations

from datetime import datetime, timezone

import card_domain as domain

NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


def _state(used_credit=0, processed=frozenset()):
    return domain.CardState(used_credit=used_credit, processed=processed)


def _event(**overrides):
    base = {
        "type": "purchase_requested",
        "request_id": "req-1",
        "card_id": "card-1",
        "card_account_id": "acct-1",
        "amount_usd": 50000,
        "credit_limit": 100000,
        "installments": 1,
    }
    base.update(overrides)
    return base


def test_approval_updates_used_credit_state():
    decision = domain.decide(_state(used_credit=0), _event(amount_usd=50000), NOW)
    assert decision.new_used_credit == 50000
    assert decision.card_events[0]["type"] == "purchase_approved"
    assert decision.status_events[0]["status"] == "approved"


def test_decline_at_limit_leaves_used_credit_unchanged():
    # used_credit=900, event amount=200, limit=1000 -> declined.
    decision = domain.decide(
        _state(used_credit=900), _event(amount_usd=200, credit_limit=1000), NOW
    )
    assert decision.new_used_credit is None
    assert decision.card_events[0]["type"] == "purchase_declined"
    assert decision.card_events[0]["decline_reason"] == "insufficient_credit"
    assert decision.status_events[0]["status"] == "declined"


def test_installments_reserve_the_full_amount_immediately():
    # $900 in 9 installments on a $1,000 limit -> used_credit becomes $900
    # (not $100/installment), and a subsequent $150 purchase must be declined.
    first = domain.decide(
        _state(used_credit=0),
        _event(amount_usd=90000, credit_limit=100000, installments=9, request_id="req-a"),
        NOW,
    )
    assert first.new_used_credit == 90000

    second = domain.decide(
        _state(used_credit=90000),
        _event(amount_usd=15000, credit_limit=100000, installments=1, request_id="req-b"),
        NOW,
    )
    assert second.new_used_credit is None
    assert second.card_events[0]["type"] == "purchase_declined"


def test_duplicate_request_is_a_noop():
    processed = frozenset({"req-1"})
    decision = domain.decide(_state(used_credit=0, processed=processed), _event(), NOW)
    assert decision == domain.Decision.noop()


def test_fresh_limit_per_event_is_honored_not_stale_state():
    # Same used_credit, but this event embeds a HIGHER limit than a prior one
    # would have — the decision must use THIS event's limit, never a cached one.
    decision = domain.decide(
        _state(used_credit=900), _event(amount_usd=200, credit_limit=2000), NOW
    )
    assert decision.new_used_credit == 1100
    assert decision.card_events[0]["type"] == "purchase_approved"


def test_applied_rate_is_omitted_entirely_when_no_conversion():
    decision = domain.decide(_state(used_credit=0), _event(), NOW)
    assert "applied_rate" not in decision.card_events[0]


def test_applied_rate_is_included_when_conversion_present():
    # Must match the real key the router publishes on `purchase_requested`
    # (see card_router.py) — using any other key here would silently mask
    # a mismatch between the event producer and this consumer, as happened
    # before this fix (the field was previously read as "conversion").
    applied_rate = {"applied_rate": "1.10", "from_currency": "EUR"}
    decision = domain.decide(
        _state(used_credit=0), _event(applied_rate=applied_rate), NOW
    )
    assert decision.card_events[0]["applied_rate"] == applied_rate
