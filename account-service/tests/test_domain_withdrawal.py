"""RED for the withdrawal domain branch — mirrors test_domain_deposit.py's style,
but without the defensive multi-field probing (we know the exact field name)."""

from domain import (
    LEG_WITHDRAWAL,
    Decision,
    LedgerState,
    decide,
    dedup_key,
)

TS = "2026-09-09T12:00:00Z"


def state(balance=100000, processed=frozenset()):
    return LedgerState(balance=balance, processed=processed)


def withdrawal_event(
    request_id="r1",
    amount_applied=45540,
    currency="EUR",
    applied_rate=None,
    admin_id="admin-42",
    reason="atm withdrawal",
):
    evt = {
        "type": "withdrawal",
        "request_id": request_id,
        "account_id": "1234567890123456",
        "amount": 50000,
        "currency": currency,
        "amount_applied": amount_applied,
        "admin_id": admin_id,
        "ts": TS,
        "leg": LEG_WITHDRAWAL,
    }
    if applied_rate is not None:
        evt["applied_rate"] = applied_rate
    if reason is not None:
        evt["reason"] = reason
    return evt


def test_approved_withdrawal_decrements_balance_and_emits_events():
    event = withdrawal_event(request_id="r1", amount_applied=45540)
    decision = decide("1234567890123456", event, state(balance=100000), now=TS)

    assert decision.new_balance == 54460
    assert len(decision.balance_events) == 1
    assert decision.balance_events[0]["balance"] == 54460

    assert len(decision.account_events) == 1
    assert decision.account_events[0]["type"] == "withdrawal_confirmed"
    assert decision.account_events[0]["amount"] == 45540

    assert len(decision.withdrawal_status_events) == 1
    status = decision.withdrawal_status_events[0]
    assert status["request_id"] == "r1"
    assert status["status"] == "approved"
    assert status["new_balance"] == 54460
    assert status["amount_applied"] == 45540


def test_insufficient_funds_declines_and_leaves_balance_untouched():
    event = withdrawal_event(request_id="r2", amount_applied=200000)
    decision = decide("1234567890123456", event, state(balance=100000), now=TS)

    assert decision.new_balance is None
    assert decision.balance_events == ()

    assert len(decision.account_events) == 1
    assert decision.account_events[0]["type"] == "declined_withdrawal"
    assert decision.account_events[0]["reason"] == "insufficient_funds"

    assert len(decision.withdrawal_status_events) == 1
    status = decision.withdrawal_status_events[0]
    assert status["status"] == "declined"
    assert status["reason"] == "insufficient_funds"


def test_invalid_amount_declines():
    event = withdrawal_event(request_id="r3", amount_applied=0)
    decision = decide("1234567890123456", event, state(balance=100000), now=TS)

    assert decision.new_balance is None
    assert decision.balance_events == ()
    assert decision.account_events[0]["type"] == "declined_withdrawal"
    assert decision.account_events[0]["reason"] == "invalid_amount"
    assert decision.withdrawal_status_events[0]["status"] == "declined"
    assert decision.withdrawal_status_events[0]["reason"] == "invalid_amount"


def test_dedup_noop_on_replayed_request():
    event = withdrawal_event(request_id="r1", amount_applied=45540)
    key = dedup_key("r1", LEG_WITHDRAWAL)
    decision = decide("1234567890123456", event, state(balance=100000, processed=frozenset({key})), now=TS)

    assert decision == Decision.noop()
    assert decision.new_balance is None
    assert decision.balance_events == ()


def test_cross_currency_approved_withdrawal_carries_applied_rate():
    applied_rate = {"pair": "USD_EUR", "mid_rate": 0.92, "applied_rate": 0.9108}
    event = withdrawal_event(request_id="r4", amount_applied=45540, applied_rate=applied_rate)
    decision = decide("1234567890123456", event, state(balance=100000), now=TS)

    assert decision.account_events[0]["applied_rate"] == applied_rate
    assert decision.withdrawal_status_events[0]["applied_rate"] == applied_rate


def test_same_currency_withdrawal_omits_applied_rate():
    event = withdrawal_event(request_id="r5", amount_applied=45540, applied_rate=None)
    decision = decide("1234567890123456", event, state(balance=100000), now=TS)

    assert "applied_rate" not in decision.account_events[0]
    assert "applied_rate" not in decision.withdrawal_status_events[0]
