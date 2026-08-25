"""Tests for the HTTP/WebSocket surface (spec §6)."""
import json
import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.config import Settings
from gateway.status_registry import StatusRegistry


class FakePublisher:
    def __init__(self):
        self.published = []

    def publish(self, topic, key, value):
        self.published.append((topic, key, value))


@pytest.fixture
def context():
    publisher, registry = FakePublisher(), StatusRegistry()
    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2)
    app = create_app(settings=settings, publisher=publisher, registry=registry)
    with TestClient(app) as client:
        yield client, publisher, registry


def test_transfer_is_accepted_without_waiting_for_the_ledger(context):
    client, publisher, _ = context

    response = client.post(
        "/transfer",
        json={"source_account": "acc-123", "destination_account": "acc-456", "amount": 1100},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["request_id"]
    assert body["fee_amount"] == 25


def test_transfer_is_published_to_account_events_keyed_by_source(context):
    client, publisher, _ = context

    body = client.post(
        "/transfer",
        json={"source_account": "acc-123", "destination_account": "acc-456", "amount": 1100},
    ).json()

    assert len(publisher.published) == 1
    topic, key, event = publisher.published[0]
    assert topic == "account-events"
    assert key == "acc-123"
    assert event["type"] == "transfer_requested"
    assert event["request_id"] == body["request_id"]
    assert event["amount"] == 1100
    assert event["fee_amount"] == 25
    assert event["source_account"] == "acc-123"
    assert event["destination_account"] == "acc-456"
    assert event["fees_account"]


def test_each_request_gets_its_own_id(context):
    client, _, _ = context
    payload = {"source_account": "a", "destination_account": "b", "amount": 100}
    first = client.post("/transfer", json=payload).json()["request_id"]
    second = client.post("/transfer", json=payload).json()["request_id"]
    assert first != second


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amounts_are_rejected(context, amount):
    client, publisher, _ = context
    response = client.post(
        "/transfer",
        json={"source_account": "a", "destination_account": "b", "amount": amount},
    )
    assert response.status_code == 422
    assert publisher.published == []


def test_blank_accounts_are_rejected(context):
    client, publisher, _ = context
    response = client.post(
        "/transfer",
        json={"source_account": "  ", "destination_account": "b", "amount": 100},
    )
    assert response.status_code == 422
    assert publisher.published == []


def test_status_is_pending_until_the_ledger_answers(context):
    client, _, _ = context
    response = client.get("/transfer/req-unknown/status")
    assert response.status_code == 200
    assert response.json() == {"request_id": "req-unknown", "status": "pending"}


def test_status_reflects_a_resolved_transfer(context):
    client, _, registry = context
    registry.resolve({"request_id": "req-1", "status": "approved", "account_id": "acc-1"})

    assert client.get("/transfer/req-1/status").json()["status"] == "approved"


def test_websocket_pushes_an_already_resolved_status_immediately(context):
    client, _, registry = context
    registry.resolve({"request_id": "req-1", "status": "declined", "reason": "insufficient_funds"})

    with client.websocket_connect("/ws/transfer/req-1") as ws:
        message = ws.receive_json()

    assert message["status"] == "declined"
    assert message["reason"] == "insufficient_funds"


def test_websocket_times_out_to_pending_rather_than_hanging_forever(context):
    client, _, _ = context
    with client.websocket_connect("/ws/transfer/req-never") as ws:
        assert ws.receive_json()["status"] == "pending"


def test_health_reports_ok(context):
    client, _, _ = context
    assert client.get("/health").json()["status"] == "ok"
