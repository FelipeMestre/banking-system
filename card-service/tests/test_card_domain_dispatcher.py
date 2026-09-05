"""RED for the card-service event-type dispatcher and `card_payment_received`
branch (Credit Cards Phase 3 — task 6). `domain.py::decide()` previously
assumed every event was `purchase_requested`; this introduces a real
dispatcher wrapping that existing logic as its first branch — see
`test_card_domain.py` for the untouched purchase-flow regression suite this
file must not break.
"""
from __future__ import annotations

from datetime import datetime, timezone

import card_domain as domain

NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


def _state(used_credit=0, processed=frozenset()):
    return domain.CardState(used_credit=used_credit, processed=processed)


def _payment_event(**overrides):
    base = {
        "type": "card_payment_received",
        "request_id": "pay-1",
        "card_account_id": "acct-1",
        "card_id": "card-1",
        "amount_usd": 20000,
    }
    base.update(overrides)
    return base


# --- existing purchase flow unaffected (regression, task 6) ------------------


def test_purchase_requested_still_dispatches_through_the_new_dispatcher():
    purchase_event = {
        "type": "purchase_requested",
        "request_id": "req-1",
        "card_id": "card-1",
        "card_account_id": "acct-1",
        "amount_usd": 50000,
        "credit_limit": 100000,
        "installments": 1,
    }
    decision = domain.decide(_state(used_credit=0), purchase_event, NOW)
    assert decision.new_used_credit == 50000
    assert decision.card_events[0]["type"] == "purchase_approved"


# --- card_payment_received: reduces used_credit, no credit-limit check ------


def test_payment_reduces_used_credit():
    decision = domain.decide(_state(used_credit=50000), _payment_event(amount_usd=20000), NOW)
    assert decision.new_used_credit == 30000
    assert decision.card_events[0]["type"] == "payment_applied"


def test_overpayment_drives_used_credit_negative_with_no_rejection_or_clamping():
    decision = domain.decide(_state(used_credit=10000), _payment_event(amount_usd=15000), NOW)
    assert decision.new_used_credit == -5000
    assert decision.card_events[0]["type"] == "payment_applied"
    assert decision.payment_status_events[0]["status"] == "approved"


def test_payment_applied_event_carries_request_id_and_amount():
    decision = domain.decide(
        _state(used_credit=0), _payment_event(request_id="pay-9", amount_usd=7500), NOW
    )
    applied = decision.card_events[0]
    assert applied["request_id"] == "pay-9"
    assert applied["card_account_id"] == "acct-1"
    assert applied["card_id"] == "card-1"
    assert applied["amount_usd"] == 7500


def test_payment_emits_card_payment_status_approved():
    decision = domain.decide(_state(used_credit=0), _payment_event(), NOW)
    assert len(decision.payment_status_events) == 1
    assert decision.payment_status_events[0]["status"] == "approved"
    assert decision.payment_status_events[0]["request_id"] == "pay-1"
    assert decision.status_events == ()


def test_duplicate_payment_request_is_a_noop():
    processed = frozenset({"pay-1"})
    decision = domain.decide(_state(used_credit=0, processed=processed), _payment_event(), NOW)
    assert decision == domain.Decision.noop()


def test_unknown_event_type_is_a_noop():
    decision = domain.decide(_state(used_credit=0), {"type": "who_knows", "request_id": "x"}, NOW)
    assert decision == domain.Decision.noop()
