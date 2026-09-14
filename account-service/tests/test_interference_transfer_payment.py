"""Same-key interference test (Credit Cards Phase 3 — task 9, design-mandated).

A `transfer_requested` event immediately followed/preceded by a
`payment_requested` event on the SAME keyed account stream must produce two
independent, uncorrupted state transitions: `processed_ids`/`balance` keyed
state is not cross-contaminated between the two event types, even though both
share the account's own key and both mutate `balance`. Pure-function harness
(no Flink runtime needed): folds `decide()`'s output back into `LedgerState`
exactly the way `AccountProcessor.process_element` does, mirroring
`test_domain.py::test_two_requests_on_the_same_account_apply_in_order_without_lost_updates`'s
established pattern for a single event type, extended to two types.
"""
from __future__ import annotations

from domain import Decision, LedgerState, decide

TS = "2026-09-04T10:00:00Z"


def transfer_requested(request_id="req-transfer", amount=1000, fee_amount=25):
    return {
        "type": "transfer_requested",
        "request_id": request_id,
        "source_account": "acc-shared",
        "destination_account": "acc-dst",
        "fees_account": "acc-fees",
        "amount": amount,
        "fee_amount": fee_amount,
        "ts": TS,
    }


def payment_requested(request_id="req-payment", amount=2000):
    return {
        "type": "payment_requested",
        "request_id": request_id,
        "destination_account": "4111111111111111",
        "card_account_id": "card-acct-1",
        "card_id": "card-1",
        "amount": amount,
        "ts": TS,
    }


def apply(decision: Decision, state: LedgerState) -> LedgerState:
    balance = state.balance if decision.new_balance is None else decision.new_balance
    return LedgerState(balance=balance, processed=state.processed | set(decision.dedup_keys))


def empty(balance=0) -> LedgerState:
    return LedgerState(balance=balance, processed=frozenset())


def test_transfer_then_payment_on_the_same_account_resolve_independently():
    state = empty(balance=10000)

    transfer_decision = decide("acc-shared", transfer_requested(amount=1000, fee_amount=25), state, now=TS)
    state = apply(transfer_decision, state)
    assert state.balance == 10000 - 1025

    payment_decision = decide("acc-shared", payment_requested(amount=2000), state, now=TS)
    state = apply(payment_decision, state)
    assert state.balance == 10000 - 1025 - 2000

    # Independent outcomes: the transfer produced its 3-way fan-out, the
    # payment produced its single outgoing_payment + card_payment_received.
    assert [e["type"] for e in transfer_decision.account_events] == [
        "outgoing_payment", "incoming_payment", "incoming_payment",
    ]
    assert [e["type"] for e in payment_decision.account_events] == ["outgoing_payment"]
    assert payment_decision.card_events[0]["type"] == "card_payment_received"


def test_payment_then_transfer_on_the_same_account_resolve_independently():
    state = empty(balance=10000)

    payment_decision = decide("acc-shared", payment_requested(amount=2000), state, now=TS)
    state = apply(payment_decision, state)
    assert state.balance == 8000

    transfer_decision = decide("acc-shared", transfer_requested(amount=1000, fee_amount=25), state, now=TS)
    state = apply(transfer_decision, state)
    assert state.balance == 8000 - 1025

    assert [e["type"] for e in transfer_decision.account_events] == [
        "outgoing_payment", "incoming_payment", "incoming_payment",
    ]


def test_dedup_keys_do_not_cross_contaminate_between_event_types_sharing_request_id():
    """Two events of DIFFERENT types sharing the SAME request_id must be
    treated as two independent units of work, not one, because the dedup key
    is (request_id, leg/type) — never request_id alone."""
    state = empty(balance=10000)
    shared_id = "shared-request-id"

    transfer_decision = decide(
        "acc-shared", transfer_requested(request_id=shared_id, amount=1000, fee_amount=25), state, now=TS
    )
    state = apply(transfer_decision, state)
    assert transfer_decision != Decision.noop()

    payment_decision = decide(
        "acc-shared", payment_requested(request_id=shared_id, amount=2000), state, now=TS
    )
    # Must NOT be treated as a duplicate of the transfer just because the
    # request_id matches — the payment's own dedup key is distinct.
    assert payment_decision != Decision.noop()
    assert payment_decision.new_balance == 10000 - 1025 - 2000


def test_replaying_the_transfer_after_the_payment_is_still_a_noop():
    """Replaying the ORIGINAL transfer request after an interleaved payment
    must remain a noop — the payment must not have consumed or altered the
    transfer's own dedup entry."""
    state = empty(balance=10000)

    transfer_decision = decide("acc-shared", transfer_requested(), state, now=TS)
    state = apply(transfer_decision, state)

    payment_decision = decide("acc-shared", payment_requested(), state, now=TS)
    state = apply(payment_decision, state)

    replayed = decide("acc-shared", transfer_requested(), state, now=TS)
    assert replayed == Decision.noop()
