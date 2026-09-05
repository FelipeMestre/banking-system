"""RED for the account-service `payment_requested` branch (Credit Cards Phase
3 — tasks 3 & 9). Added as a 5th `if` in `decide()`; zero lines of the
existing 4 branches (transfer/incoming/outgoing/declined) are touched by this
file's assertions — see `test_domain.py` for the untouched regression suite.
"""
from __future__ import annotations

from domain import STATUS_APPROVED, STATUS_DECLINED, Decision, LedgerState, decide, dedup_key

TS = "2026-09-04T10:00:00Z"


def payment_requested(
    request_id="pay-1",
    destination_account="4111111111111111",
    card_account_id="card-acct-1",
    card_id="card-1",
    amount=20000,
    amount_usd=None,
    conversion=None,
):
    event = {
        "type": "payment_requested",
        "request_id": request_id,
        "destination_account": destination_account,
        "card_account_id": card_account_id,
        "card_id": card_id,
        "amount": amount,
        "ts": TS,
    }
    if amount_usd is not None:
        event["amount_usd"] = amount_usd
    if conversion is not None:
        event["conversion"] = conversion
    return event


def empty(balance=0) -> LedgerState:
    return LedgerState(balance=balance, processed=frozenset())


# --- sufficient funds --------------------------------------------------------


def test_sufficient_funds_debits_balance_and_emits_outgoing_payment():
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=50000), now=TS)

    assert decision.new_balance == 30000
    assert dedup_key("pay-1", "payment") in decision.dedup_keys
    outgoing = decision.account_events[0]
    assert outgoing["type"] == "outgoing_payment"
    assert outgoing["destination_account"] == "4111111111111111"
    assert outgoing["amount"] == 20000


def test_sufficient_funds_emits_card_payment_received_keyed_by_card_account_id():
    decision = decide(
        "acc-pay", payment_requested(card_account_id="card-acct-9", amount=20000), empty(balance=50000), now=TS
    )

    assert len(decision.card_events) == 1
    card_event = decision.card_events[0]
    assert card_event["type"] == "card_payment_received"
    assert card_event["card_account_id"] == "card-acct-9"
    assert card_event["amount_usd"] == 20000


def test_card_payment_received_carries_the_card_id_for_the_movement_row():
    decision = decide(
        "acc-pay", payment_requested(card_id="card-42", amount=20000), empty(balance=50000), now=TS
    )
    assert decision.card_events[0]["card_id"] == "card-42"


def test_sufficient_funds_emits_card_payment_status_approved():
    decision = decide("acc-pay", payment_requested(), empty(balance=50000), now=TS)

    assert len(decision.card_status_events) == 1
    status = decision.card_status_events[0]
    assert status["status"] == STATUS_APPROVED
    assert status["request_id"] == "pay-1"


def test_amount_usd_defaults_to_amount_when_no_conversion():
    decision = decide("acc-pay", payment_requested(amount=15000), empty(balance=50000), now=TS)
    assert decision.card_events[0]["amount_usd"] == 15000


def test_amount_usd_uses_converted_value_when_present():
    decision = decide(
        "acc-pay", payment_requested(amount=18000, amount_usd=20000), empty(balance=50000), now=TS
    )
    assert decision.card_events[0]["amount_usd"] == 20000


def test_conversion_is_attached_to_the_outgoing_payment_event_when_present():
    conversion = {"pair": "EUR_USD", "direction": "debit", "mid_rate": "1.10",
                  "applied_rate": "1.12", "margin": "0.02", "source_ts": TS}
    decision = decide(
        "acc-pay", payment_requested(amount=18000, conversion=conversion), empty(balance=50000), now=TS
    )
    assert decision.account_events[0]["conversion"] == conversion


def test_no_conversion_key_present_when_conversion_absent():
    decision = decide("acc-pay", payment_requested(), empty(balance=50000), now=TS)
    assert "conversion" not in decision.account_events[0]


def test_balance_event_announces_the_post_debit_balance():
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=50000), now=TS)
    assert decision.balance_events == ({"account_id": "acc-pay", "balance": 30000, "ts": TS},)


# --- insufficient funds -------------------------------------------------------


def test_insufficient_funds_declines_without_touching_balance():
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=100), now=TS)

    assert decision.new_balance is None
    assert [e["type"] for e in decision.account_events] == ["declined_payment"]
    assert decision.account_events[0]["reason"] == "insufficient_funds"


def test_insufficient_funds_emits_zero_card_events():
    """Explicit negative assertion: NO event of any kind reaches `card-events`
    when the paying account cannot cover the payment (spec: card-account-
    payments-api Insufficient funds scenario)."""
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=100), now=TS)

    assert decision.card_events == ()


def test_insufficient_funds_emits_zero_card_status_events():
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=100), now=TS)
    assert decision.card_status_events == ()


def test_insufficient_funds_emits_zero_balance_events():
    decision = decide("acc-pay", payment_requested(amount=20000), empty(balance=100), now=TS)
    assert decision.balance_events == ()


# --- dedup / idempotency -------------------------------------------------------


def test_duplicate_payment_requested_is_a_silent_noop():
    state = empty(balance=50000)
    first = decide("acc-pay", payment_requested(), state, now=TS)
    state = LedgerState(balance=first.new_balance, processed=state.processed | set(first.dedup_keys))

    second = decide("acc-pay", payment_requested(), state, now=TS)
    assert second == Decision.noop()


def test_a_declined_payment_stays_declined_even_if_funds_arrive_later():
    state = empty(balance=0)
    first = decide("acc-pay", payment_requested(amount=100), state, now=TS)
    state = LedgerState(balance=state.balance, processed=state.processed | set(first.dedup_keys))

    state = LedgerState(balance=9999, processed=state.processed)
    assert decide("acc-pay", payment_requested(amount=100), state, now=TS) == Decision.noop()


# --- interference with transfer_requested on the same key (task 9) ----------


def test_payment_requested_dedup_key_does_not_collide_with_transfer_requested():
    """A `transfer_requested` and a `payment_requested` sharing the same
    `request_id` on the same keyed account must not be treated as the same
    unit of work — the dedup key is per-leg-per-type."""
    from domain import LEG_DEBIT, dedup_key as _dedup_key

    transfer_key = _dedup_key("shared-id", LEG_DEBIT)
    payment_key = _dedup_key("shared-id", "payment")
    assert transfer_key != payment_key
