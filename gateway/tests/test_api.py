"""Tests for the HTTP/WebSocket surface (spec §6)."""
import json
import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.config import Settings


class FakePublisher:
    def __init__(self):
        self.published = []

    def publish(self, topic, key, value):
        self.published.append((topic, key, value))


@pytest.fixture
def context():
    publisher = FakePublisher()
    app = create_app(settings=Settings(fee_flat_cents=25), publisher=publisher)
    with TestClient(app) as client:
        yield client, publisher


def test_transfer_is_accepted_without_waiting_for_the_ledger(context):
    client, publisher = context

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
    client, publisher = context

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
    client, _ = context
    payload = {"source_account": "a", "destination_account": "b", "amount": 100}
    first = client.post("/transfer", json=payload).json()["request_id"]
    second = client.post("/transfer", json=payload).json()["request_id"]
    assert first != second


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amounts_are_rejected(context, amount):
    client, publisher = context
    response = client.post(
        "/transfer",
        json={"source_account": "a", "destination_account": "b", "amount": amount},
    )
    assert response.status_code == 422
    assert publisher.published == []


def test_blank_accounts_are_rejected(context):
    client, publisher = context
    response = client.post(
        "/transfer",
        json={"source_account": "  ", "destination_account": "b", "amount": 100},
    )
    assert response.status_code == 422
    assert publisher.published == []

def test_health_reports_ok(context):
    client, _ = context
    assert client.get("/health").json()["status"] == "ok"
