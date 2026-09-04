"""RED for Credit Cards Phase 1: `POST /cards/{card_number}/status` (T24)."""
from __future__ import annotations

import uuid

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository, FakeCardAccountRepository, FakeCardRepository


@pytest.fixture
def cards_harness():
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


def test_blocking_a_card_leaves_the_card_account_active(cards_harness):
    issued = _issue(cards_harness).json()
    card_number = issued["card"]["card_number"]
    card_account_id = issued["card_account"]["id"]

    response = cards_harness.client.post(f"/cards/{card_number}/status", json={"status": "blocked"})

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    account = cards_harness.card_accounts.rows[uuid.UUID(card_account_id)]
    assert account.status.value == "active"


def test_reactivating_a_blocked_card(cards_harness):
    issued = _issue(cards_harness).json()
    card_number = issued["card"]["card_number"]
    cards_harness.client.post(f"/cards/{card_number}/status", json={"status": "blocked"})

    response = cards_harness.client.post(f"/cards/{card_number}/status", json={"status": "active"})

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_a_nonexistent_card_number_returns_404(cards_harness):
    response = cards_harness.client.post("/cards/9999999999999999/status", json={"status": "blocked"})
    assert response.status_code == 404


def test_response_masks_the_card_number(cards_harness):
    issued = _issue(cards_harness).json()
    card_number = issued["card"]["card_number"]

    response = cards_harness.client.post(f"/cards/{card_number}/status", json={"status": "blocked"})

    assert response.json()["card_number"].startswith("•••• •••• •••• ")
