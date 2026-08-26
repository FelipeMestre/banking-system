"""Payment surface. Behaviour must be identical to v1 (spec §8.1)."""
from __future__ import annotations

import pytest

from openbankapi.domain.service import compute_fee

SOURCE = "1234567890123456"
DEST = "6543210987654321"


def test_flat_fee_matches_the_spec_example():
    assert compute_fee(1100, flat_fee_cents=25) == 25


def test_the_fee_never_exceeds_the_amount():
    assert compute_fee(10, flat_fee_cents=25) == 10


def test_transfer_is_accepted_without_waiting_for_the_ledger(harness):
    response = harness.client.post(
        "/transfer",
        json={"source_account": SOURCE, "destination_account": DEST, "amount": 1100},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["fee_amount"] == 25


def test_the_event_is_keyed_by_source_and_matches_the_spec_schema(harness):
    body = harness.client.post(
        "/transfer",
        json={"source_account": SOURCE, "destination_account": DEST, "amount": 1100},
    ).json()

    assert len(harness.publisher.published) == 1
    topic, key, event = harness.publisher.published[0]
    assert topic == "account-events"
    assert key == SOURCE
    assert event["type"] == "transfer_requested"
    assert event["request_id"] == body["request_id"]
    assert event["fees_account"] == "0000000000000001"
    assert set(event) == {"type", "request_id", "source_account", "destination_account",
                          "fees_account", "amount", "fee_amount", "ts"}


def test_the_write_path_touches_no_database(harness):
    """The payment path must not depend on reference data being reachable."""
    before = harness.accounts.rows.copy()
    harness.client.post(
        "/transfer",
        json={"source_account": SOURCE, "destination_account": DEST, "amount": 500},
    )
    assert harness.accounts.rows == before


@pytest.mark.parametrize("account", ["acc-123", "123", "12345678901234567", "abcdefghijklmnop"])
def test_non_16_digit_accounts_are_rejected(harness, account):
    response = harness.client.post(
        "/transfer",
        json={"source_account": account, "destination_account": DEST, "amount": 100},
    )
    assert response.status_code == 422
    assert harness.publisher.published == []


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amounts_are_rejected(harness, amount):
    response = harness.client.post(
        "/transfer",
        json={"source_account": SOURCE, "destination_account": DEST, "amount": amount},
    )
    assert response.status_code == 422


def test_status_is_pending_until_the_ledger_answers(harness):
    response = harness.client.get("/transfer/unknown/status")
    assert response.status_code == 200
    assert response.json() == {"request_id": "unknown", "status": "pending"}


def test_status_reflects_a_resolved_transfer(harness):
    harness.registry.resolve({"request_id": "r1", "status": "approved", "account_id": SOURCE})
    assert harness.client.get("/transfer/r1/status").json()["status"] == "approved"


def test_websocket_pushes_a_resolved_verdict(harness):
    harness.registry.resolve(
        {"request_id": "r1", "status": "declined", "reason": "insufficient_funds"}
    )
    with harness.client.websocket_connect("/ws/transfer/r1") as ws:
        message = ws.receive_json()
    assert message["status"] == "declined"
    assert message["reason"] == "insufficient_funds"


def test_websocket_times_out_to_pending_rather_than_hanging(harness):
    with harness.client.websocket_connect("/ws/transfer/never") as ws:
        assert ws.receive_json()["status"] == "pending"


def test_health(harness):
    assert harness.client.get("/health").json()["status"] == "ok"
