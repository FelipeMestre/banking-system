"""RED for Task 4.1 — Flink domain deposit branch."""

from domain import LEG_DEPOSIT, Decision, LedgerState, decide, dedup_key

TS = "2026-09-07T12:00:00Z"


def empty(balance=100000):
    return LedgerState(balance=balance, processed=frozenset())


def deposit_event(request_id="r1", amount_applied=45540, currency="EUR", applied_rate=None, admin_id="admin-42", reason="cash branch 42"):
    evt = {
        "type": "deposit",
        "request_id": request_id,
        "account_id": "1234567890123456",
        "amount": 50000,
        "currency": currency,
        "amount_applied": amount_applied,
        "admin_id": admin_id,
        "ts": TS,
        "leg": LEG_DEPOSIT,
    }
    if applied_rate is not None:
        evt["applied_rate"] = applied_rate
    if reason is not None:
        evt["reason"] = reason
    return evt


def test_deposit_cross_currency_creates_new_balance_and_events():
    event = deposit_event(request_id="r1", amount_applied=45540, currency="EUR", applied_rate={"pair": "USD_EUR", "mid_rate": 0.92, "applied_rate": 0.9108})
    decision = decide("1234567890123456", event, empty(balance=100000), now=TS)
    assert decision.new_balance == 145540
    assert len(decision.balance_events) == 1
    assert decision.balance_events[0]["balance"] == 145540
    assert len(decision.account_events) == 1
    assert decision.account_events[0]["type"] == "deposit_confirmed"
    # status events: either status_events or deposit_status_events depending on impl; check both
    status_events = getattr(decision, "status_events", ()) or getattr(decision, "deposit_status_events", ())
    # fallback: if deposit uses status_events
    if not status_events and hasattr(decision, "deposit_status_events"):
        status_events = decision.deposit_status_events
    # If still none, try any field containing deposit status
    assert len(status_events) == 1 or len(decision.status_events) == 1
    # Normalize to check
    found = None
    for cand in [getattr(decision, "status_events", ()), getattr(decision, "deposit_status_events", ()), getattr(decision, "card_status_events", ())]:
        for e in cand:
            if e.get("request_id") == "r1" and e.get("status") == "approved":
                found = e
    assert found is not None
    assert found["new_balance"] == 145540
    assert found["amount_applied"] == 45540


def test_deposit_same_currency_omits_applied_rate():
    event = deposit_event(request_id="r2", amount_applied=50000, currency="EUR", applied_rate=None)
    # remove applied_rate to test omit
    event.pop("applied_rate", None)
    decision = decide("1234567890123456", event, empty(balance=100000), now=TS)
    assert decision.new_balance == 150000
    # deposit_confirmed should omit applied_rate when None
    assert decision.account_events[0]["type"] == "deposit_confirmed"
    assert "applied_rate" not in decision.account_events[0]
    # deposit-status should also omit
    status_events = decision.status_events if hasattr(decision, "status_events") else ()
    # also check alternative field
    if hasattr(decision, "deposit_status_events"):
        status_events = status_events or decision.deposit_status_events
    found = None
    for e in status_events:
        if e.get("request_id") == "r2":
            found = e
            break
    if found is None:
        # try any status-like field
        for attr in ["status_events", "deposit_status_events", "card_status_events"]:
            for e in getattr(decision, attr, ()):
                if e.get("request_id") == "r2":
                    found = e
                    break
    assert found is not None
    assert "applied_rate" not in found or found.get("applied_rate") is None


def test_deposit_dedup_noop():
    event = deposit_event(request_id="r1", amount_applied=45540)
    key = dedup_key("r1", LEG_DEPOSIT)
    state = LedgerState(balance=100000, processed=frozenset({key}))
    decision = decide("1234567890123456", event, state, now=TS)
    assert decision == Decision.noop()
    assert decision.new_balance is None
    assert decision.balance_events == ()


def test_deposit_uses_dedup_key_with_leg():
    event = deposit_event(request_id="r1", amount_applied=45540)
    decision = decide("1234567890123456", event, empty(balance=0), now=TS)
    assert dedup_key("r1", LEG_DEPOSIT) in decision.dedup_keys
