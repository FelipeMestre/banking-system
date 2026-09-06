"""RED for Credit Cards Phase 3: `POST /card-accounts/{card_account_id}/payments`
(task 2). Mirrors `test_purchase_router.py`'s harness pattern exactly."""
from __future__ import annotations

import uuid

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository, FakeCardAccountRepository, FakeCardRepository


@pytest.fixture
def payments_harness():
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
    h = build(accounts=accounts)
    with h.client:
        account_response = h.client.post(
            "/accounts", json={"currency": "USD", "customer_id": str(customer_id), "branch_id": str(branch_id)}
        )
    paying_account = accounts.rows[account_response.json()["account_number"]]

    card_accounts = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account.id})
    cards = FakeCardRepository()
    h2 = build(accounts=accounts, card_accounts=card_accounts, cards=cards)
    h2.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|test"}
    h2.customer_id, h2.paying_account_id, h2.paying_account = customer_id, paying_account.id, paying_account
    with h2.client:
        yield h2


def _issue(h):
    return h.client.post(
        "/card-accounts",
        json={
            "customer_id": str(h.customer_id),
            "paying_account_id": str(h.paying_account_id),
            "credit_limit": "1500.00",
        },
    )


def _pay(h, card_account_id, **overrides):
    payload = {"amount": 20000}
    payload.update(overrides)
    return h.client.post(f"/card-accounts/{card_account_id}/payments", json=payload)


def test_payment_on_unknown_card_account_returns_404(payments_harness):
    response = _pay(payments_harness, str(uuid.uuid4()))
    assert response.status_code == 404


def test_payment_with_no_active_card_returns_409(payments_harness):
    issued = _issue(payments_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = uuid.UUID(issued["card"]["id"])
    payments_harness.cards.rows[card_id] = payments_harness.cards.rows[card_id].__class__(
        **{**payments_harness.cards.rows[card_id].__dict__, "status": payments_harness.cards.rows[card_id].status.__class__("blocked")}
    )

    response = _pay(payments_harness, card_account_id)

    assert response.status_code == 409


def test_happy_path_publishes_payment_requested_keyed_by_paying_account_number(payments_harness):
    issued = _issue(payments_harness).json()
    card_account_id = issued["card_account"]["id"]

    response = _pay(payments_harness, card_account_id, amount=20000)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert "request_id" in body

    assert len(payments_harness.publisher.published) == 1
    topic, key, value = payments_harness.publisher.published[0]
    assert topic == payments_harness.settings.account_events_topic
    assert key == payments_harness.paying_account.account_number
    assert value["type"] == "payment_requested"
    assert value["amount"] == 20000
    assert value["destination_account"] == issued["card"]["card_number"]
    assert value["card_account_id"] == card_account_id
    assert value["card_id"] == issued["card"]["id"]
