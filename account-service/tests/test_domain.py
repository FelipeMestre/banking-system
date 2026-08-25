"""Tests for the pure account decision logic (spec §5.3 and §9)."""
import pytest

from domain import (
    LEG_CREDIT_DESTINATION,
    LEG_DEBIT,
    Decision,
    LedgerState,
    decide,
    dedup_key,
    shard_key_of,
)

TS = "2026-08-24T14:02:01Z"


def transfer_requested(
    request_id="req-1",
    source="acc-src",
    destination="acc-dst",
    fees="acc-fees",
    amount=1100,
    fee_amount=25,
):
    return {
        "type": "transfer_requested",
        "request_id": request_id,
        "source_account": source,
        "destination_account": destination,
        "fees_account": fees,
        "amount": amount,
        "fee_amount": fee_amount,
        "ts": TS,
    }


def apply(decision: Decision, state: LedgerState) -> LedgerState:
    """Fold a decision into the in-test account state, like the Flink operator does."""
    balance = state.balance if decision.new_balance is None else decision.new_balance
    return LedgerState(balance=balance, processed=state.processed | set(decision.dedup_keys))


def empty(balance=0) -> LedgerState:
    return LedgerState(balance=balance, processed=frozenset())


# --- shard key extraction (spec §3.1, §5.1) ---------------------------------


def test_transfer_requested_shards_on_source_account():
    assert shard_key_of(transfer_requested(source="acc-123")) == "acc-123"


def test_other_events_shard_on_their_own_account_id():
    event = {"type": "incoming_payment", "account_id": "acc-456"}
    assert shard_key_of(event) == "acc-456"


# --- scenario 1: happy path -------------------------------------------------


def test_sufficient_balance_debits_source_and_fans_out_three_events():
    decision = decide("acc-src", transfer_requested(), empty(balance=5000), now=TS)

    assert decision.new_balance == 5000 - 1100 - 25
    assert dedup_key("req-1", LEG_DEBIT) in decision.dedup_keys

    kinds = [(e["type"], e["account_id"], e.get("amount")) for e in decision.account_events]
    assert kinds == [
        ("outgoing_payment", "acc-src", 1125),
        ("incoming_payment", "acc-dst", 1100),
        ("incoming_payment", "acc-fees", 25),
    ]
    # The approved status is not emitted here: it rides the outgoing_payment loopback.
    assert decision.status_events == ()


def test_outgoing_payment_loopback_emits_approved_and_leaves_balance_alone():
    event = {
        "type": "outgoing_payment",
        "request_id": "req-1",
        "account_id": "acc-src",
        "amount": 1125,
        "ts": TS,
    }
    decision = decide("acc-src", event, empty(balance=3875), now=TS)

    assert decision.new_balance is None
    assert [s["status"] for s in decision.status_events] == ["approved"]
    assert decision.status_events[0]["request_id"] == "req-1"
    assert decision.account_events == ()


def test_incoming_payment_credits_the_beneficiary():
    event = {
        "type": "incoming_payment",
        "request_id": "req-1",
        "account_id": "acc-dst",
        "amount": 1100,
        "leg": LEG_CREDIT_DESTINATION,
        "ts": TS,
    }
    decision = decide("acc-dst", event, empty(balance=200), now=TS)

    assert decision.new_balance == 1300
    assert decision.dedup_keys == (dedup_key("req-1", LEG_CREDIT_DESTINATION),)
    assert decision.status_events == ()


def test_end_to_end_balances_across_all_three_accounts():
    source, destination, fees = empty(balance=5000), empty(balance=0), empty(balance=0)

    requested = decide("acc-src", transfer_requested(), source, now=TS)
    source = apply(requested, source)

    for event in requested.account_events:
        account = event["account_id"]
        if account == "acc-dst":
            destination = apply(decide(account, event, destination, now=TS), destination)
        elif account == "acc-fees":
            fees = apply(decide(account, event, fees, now=TS), fees)
        else:
            source = apply(decide(account, event, source, now=TS), source)

    assert source.balance == 3875
    assert destination.balance == 1100
    assert fees.balance == 25
    assert source.balance + destination.balance + fees.balance == 5000


# --- scenario 2: insufficient funds -----------------------------------------


def test_insufficient_balance_declines_without_touching_balance():
    decision = decide("acc-src", transfer_requested(amount=1100, fee_amount=25), empty(balance=1124), now=TS)

    assert decision.new_balance is None
    assert [e["type"] for e in decision.account_events] == ["declined_payment"]
    assert decision.account_events[0]["reason"] == "insufficient_funds"
    assert decision.account_events[0]["account_id"] == "acc-src"


def test_fee_is_included_in_the_affordability_check():
    """Exactly enough for the amount but not the fee must still decline."""
    decision = decide("acc-src", transfer_requested(amount=1100, fee_amount=25), empty(balance=1100), now=TS)
    assert [e["type"] for e in decision.account_events] == ["declined_payment"]

    decision = decide("acc-src", transfer_requested(amount=1100, fee_amount=25), empty(balance=1125), now=TS)
    assert [e["type"] for e in decision.account_events] == ["outgoing_payment", "incoming_payment", "incoming_payment"]


def test_declined_payment_loopback_emits_declined_status_with_reason():
    event = {
        "type": "declined_payment",
        "request_id": "req-1",
        "account_id": "acc-src",
        "reason": "insufficient_funds",
        "ts": TS,
    }
    decision = decide("acc-src", event, empty(balance=10), now=TS)

    assert decision.new_balance is None
    assert [(s["status"], s["reason"]) for s in decision.status_events] == [
        ("declined", "insufficient_funds")
    ]


def test_unseeded_account_declines_instead_of_crashing():
    decision = decide("acc-new", transfer_requested(), LedgerState(balance=None, processed=frozenset()), now=TS)
    assert [e["type"] for e in decision.account_events] == ["declined_payment"]


# --- scenario 3: duplicate delivery (at-least-once) -------------------------


def test_duplicate_transfer_requested_is_a_silent_noop():
    state = empty(balance=5000)
    first = decide("acc-src", transfer_requested(), state, now=TS)
    state = apply(first, state)

    second = decide("acc-src", transfer_requested(), state, now=TS)

    assert second == Decision.noop()
    assert state.balance == 3875


def test_duplicate_incoming_payment_is_a_silent_noop():
    event = {
        "type": "incoming_payment",
        "request_id": "req-1",
        "account_id": "acc-dst",
        "amount": 1100,
        "leg": LEG_CREDIT_DESTINATION,
        "ts": TS,
    }
    state = empty(balance=0)
    state = apply(decide("acc-dst", event, state, now=TS), state)

    assert decide("acc-dst", event, state, now=TS) == Decision.noop()
    assert state.balance == 1100


def test_a_declined_request_stays_declined_even_if_funds_arrive_later():
    """At-least-once redelivery must not flip a settled decision."""
    state = empty(balance=0)
    state = apply(decide("acc-src", transfer_requested(), state, now=TS), state)

    state = LedgerState(balance=9999, processed=state.processed)

    assert decide("acc-src", transfer_requested(), state, now=TS) == Decision.noop()


# --- dedup keys must be per-leg, not per-request ----------------------------


def test_fee_is_not_swallowed_when_destination_equals_fees_account():
    event = transfer_requested(destination="acc-same", fees="acc-same")
    decision = decide("acc-src", event, empty(balance=5000), now=TS)

    same = empty(balance=0)
    for credit in [e for e in decision.account_events if e["type"] == "incoming_payment"]:
        same = apply(decide("acc-same", credit, same, now=TS), same)

    assert same.balance == 1125


def test_self_transfer_credits_the_source_back():
    event = transfer_requested(source="acc-x", destination="acc-x")
    state = empty(balance=5000)
    decision = decide("acc-x", event, state, now=TS)
    state = apply(decision, state)

    for produced in decision.account_events:
        if produced["account_id"] == "acc-x" and produced["type"] == "incoming_payment":
            state = apply(decide("acc-x", produced, state, now=TS), state)

    assert state.balance == 5000 - 25


# --- scenario 5: sequential application on one account ----------------------


def test_two_requests_on_the_same_account_apply_in_order_without_lost_updates():
    state = empty(balance=2000)

    first = decide("acc-src", transfer_requested("req-1", amount=1000, fee_amount=25), state, now=TS)
    state = apply(first, state)
    second = decide("acc-src", transfer_requested("req-2", amount=1000, fee_amount=25), state, now=TS)
    state = apply(second, state)

    assert [e["type"] for e in first.account_events][0] == "outgoing_payment"
    assert [e["type"] for e in second.account_events] == ["declined_payment"]
    assert state.balance == 975


# --- input validation -------------------------------------------------------


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_amounts_are_rejected(bad):
    decision = decide("acc-src", transfer_requested(amount=bad), empty(balance=5000), now=TS)
    assert decision.account_events[0]["reason"] == "invalid_amount"


def test_unknown_event_types_are_ignored():
    assert decide("acc-src", {"type": "who_knows", "account_id": "acc-src"}, empty(), now=TS) == Decision.noop()
