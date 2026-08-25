"""Tests for the pure transfer-request building logic (spec §4, §6)."""
from gateway.transfers import build_transfer_requested, compute_fee

TS = "2026-08-24T14:02:01Z"


def test_flat_fee_matches_the_spec_example():
    assert compute_fee(1100, flat_fee_cents=25) == 25


def test_fee_never_exceeds_the_amount_being_sent():
    assert compute_fee(10, flat_fee_cents=25) == 10


def test_zero_fee_is_allowed():
    assert compute_fee(1100, flat_fee_cents=0) == 0


def test_event_matches_the_spec_schema():
    event = build_transfer_requested(
        request_id="b6e1-uuid",
        source_account="acc-123",
        destination_account="acc-456",
        fees_account="acc-fees",
        amount=1100,
        fee_amount=25,
        now=TS,
    )

    assert event == {
        "type": "transfer_requested",
        "request_id": "b6e1-uuid",
        "source_account": "acc-123",
        "destination_account": "acc-456",
        "fees_account": "acc-fees",
        "amount": 1100,
        "fee_amount": 25,
        "ts": TS,
    }
