"""RED for Credit Cards Phase 2: `POST /cards/{card_number}/purchases` (T3.3-3.6)."""
from __future__ import annotations

import uuid

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.model import CardAccountStatus, CardStatus
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository, FakeCardAccountRepository, FakeCardRepository


@pytest.fixture
def purchases_harness():
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
    h2.customer_id, h2.paying_account_id = customer_id, paying_account.id
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


def _purchase(h, card_number, **overrides):
    payload = {"card_id": str(uuid.uuid4()), "amount": "50.00", "currency": "USD", "description": "coffee"}
    payload.update(overrides)
    return h.client.post(f"/cards/{card_number}/purchases", json=payload)


def test_purchase_on_unknown_card_returns_404(purchases_harness):
    response = _purchase(purchases_harness, "9999999999999999")
    assert response.status_code == 404


def test_purchase_on_blocked_card_returns_409(purchases_harness):
    issued = _issue(purchases_harness).json()
    card_number = issued["card"]["card_number"]
    purchases_harness.client.post(f"/cards/{card_number}/status", json={"status": "blocked"})

    response = _purchase(purchases_harness, card_number)

    assert response.status_code == 409


def test_purchase_on_expired_card_returns_409(purchases_harness):
    issued = _issue(purchases_harness).json()
    card_number = issued["card"]["card_number"]
    card_id = uuid.UUID(issued["card"]["id"])
    purchases_harness.cards.rows[card_id] = purchases_harness.cards.rows[card_id].__class__(
        **{**purchases_harness.cards.rows[card_id].__dict__, "status": CardStatus.EXPIRED}
    )

    response = _purchase(purchases_harness, card_number)

    assert response.status_code == 409


def test_purchase_on_closed_account_returns_409(purchases_harness):
    issued = _issue(purchases_harness).json()
    card_number = issued["card"]["card_number"]
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    purchases_harness.card_accounts.rows[card_account_id] = purchases_harness.card_accounts.rows[
        card_account_id
    ].__class__(
        **{
            **purchases_harness.card_accounts.rows[card_account_id].__dict__,
            "status": CardAccountStatus.CLOSED,
        }
    )

    response = _purchase(purchases_harness, card_number)

    assert response.status_code == 409


def test_structural_success_never_checks_credit_and_publishes_purchase_requested(purchases_harness):
    issued = _issue(purchases_harness).json()
    card_number = issued["card"]["card_number"]

    response = _purchase(purchases_harness, card_number, amount="999999999.00")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert "request_id" in body

    assert len(purchases_harness.publisher.published) == 1
    topic, key, value = purchases_harness.publisher.published[0]
    assert topic == purchases_harness.settings.card_events_topic
    assert value["type"] == "purchase_requested"
    assert value["amount_usd"] == pytest.approx(999999999.00)
    assert "credit_limit" in value
    assert key == issued["card_account"]["id"]


def test_non_usd_purchase_embeds_applied_rate(purchases_harness):
    issued = _issue(purchases_harness).json()
    card_number = issued["card"]["card_number"]

    response = _purchase(purchases_harness, card_number, amount="10.00", currency="EUR")

    assert response.status_code == 202
    _, _, value = purchases_harness.publisher.published[0]
    assert "applied_rate" in value
    assert value["applied_rate"] is not None
