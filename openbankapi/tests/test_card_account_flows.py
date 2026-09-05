"""RED for Credit Cards Phase 1: `card-accounts` endpoints (T18, T24).

TestClient + fakes — no broker, no Postgres, no Redis, matching this repo's
established e2e convention (`test_accounts.py`), not the aspirational
`httpx.AsyncClient`/testcontainers tree AGENTS.md describes for a fresh
project (this repo's own suite deviates the same way already; see
`sdd-init/banking system`'s documented testing-capabilities note).
"""
from __future__ import annotations

import uuid

import pytest

from openbankapi.config.dependencies import get_card_repository, get_current_user
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import (
    FakeAccountRepository,
    FakeCardAccountRepository,
    FakeCardRepository,
    FakeCustomerRepository,
)


def _wired_cards():
    """A harness with a real customer, a real paying account, and card
    repositories that know about both."""
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
    h2.customer_id, h2.paying_account_id = customer_id, paying_account.id
    return h2


@pytest.fixture
def cards_harness():
    h = _wired_cards()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|test"}
    with h.client:
        yield h


def _issue(h):
    return h.client.post(
        "/card-accounts",
        json={
            "customer_id": str(h.customer_id),
            "paying_account_id": str(h.paying_account_id),
            "credit_limit": "1500.00",
        },
    )


# --- Issue creates account and card atomically -------------------------------


def test_issue_creates_active_account_and_card_with_unmasked_number(cards_harness):
    response = _issue(cards_harness)
    assert response.status_code == 201
    body = response.json()
    assert body["card_account"]["status"] == "active"
    assert body["card"]["status"] == "active"
    assert len(body["card"]["card_number"]) == 16
    assert body["card"]["card_number"].isdigit()


def test_a_nonexistent_customer_is_a_clean_4xx_not_a_500(cards_harness):
    response = cards_harness.client.post(
        "/card-accounts",
        json={
            "customer_id": str(uuid.uuid4()),
            "paying_account_id": str(cards_harness.paying_account_id),
            "credit_limit": "1500.00",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ReferencedEntityNotFoundError"


def test_second_repository_failure_propagates_and_never_leaks_as_a_bare_200(cards_harness):
    """Simulates the second repository call failing mid-`issue_card_account`.

    Real atomicity (neither row surviving) is guaranteed by the shared
    request-scoped session/Unit-of-Work — see `PostgresRepository`'s and
    `CardAccountService`'s own docstrings — and is verified by code review
    plus manual/staging testing, not this single-threaded fake-backed suite
    (same documented limitation as `AccountService.open_first_account`'s
    concurrency note). What this test proves at the fake layer is that a
    mid-orchestration failure propagates through the router as an error
    rather than silently resolving to a 201 with a half-created resource.
    """
    failing_cards = FakeCardRepository()

    async def _always_fails(*, card_account_id, expiration_date):
        raise RuntimeError("simulated failure in the second repository call")

    failing_cards.create = _always_fails  # type: ignore[method-assign]
    cards_harness.client.app.dependency_overrides[get_card_repository] = lambda: failing_cards

    with pytest.raises(RuntimeError):
        _issue(cards_harness)


# --- Renewal preserves account identity --------------------------------------


def test_renewal_preserves_identity_and_replaces_the_old_card(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    old_card_number = issued["card"]["card_number"]

    response = cards_harness.client.post(f"/card-accounts/{card_account_id}/cards")

    assert response.status_code == 201
    body = response.json()
    assert body["card_account_id"] == card_account_id
    assert body["card_number"] != old_card_number
    old_card = cards_harness.cards.by_number[old_card_number]
    assert cards_harness.cards.rows[old_card].status.value == "replaced"


def test_renewal_on_a_blocked_account_returns_409(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    cards_harness.client.post(f"/card-accounts/{card_account_id}/status", json={"status": "blocked"})

    response = cards_harness.client.post(f"/card-accounts/{card_account_id}/cards")

    assert response.status_code == 409


# --- Status transitions -------------------------------------------------------


def test_invalid_account_transition_returns_409_with_domain_message(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    cards_harness.client.post(f"/card-accounts/{card_account_id}/status", json={"status": "closed"})

    response = cards_harness.client.post(f"/card-accounts/{card_account_id}/status", json={"status": "active"})

    assert response.status_code == 409
    assert "error" in response.json()


# --- List/read responses mask the card number --------------------------------


def test_get_card_account_masks_the_card_number(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]

    response = cards_harness.client.get(f"/card-accounts/{card_account_id}")

    assert response.status_code == 200
    assert response.json()["card"]["card_number"].startswith("•••• •••• •••• ")


def test_list_by_customer_masks_the_card_number(cards_harness):
    _issue(cards_harness)

    response = cards_harness.client.get(f"/card-accounts?customer_id={cards_harness.customer_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["card"]["card_number"].startswith("•••• •••• •••• ")


def test_update_credit_limit(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]

    response = cards_harness.client.put(f"/card-accounts/{card_account_id}", json={"credit_limit": "3000.00"})

    assert response.status_code == 200
    assert response.json()["credit_limit"] == "3000.00"
