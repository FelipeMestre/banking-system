"""RED for Credit Cards Phase 3: `POST /card-accounts/{card_account_id}/payments`
(task 2). Mirrors `test_card_account_movements_and_usage_router.py`'s
customer-linked harness pattern — this endpoint now resolves `CurrentCustomerDep`
to enforce that `source_account` belongs to the caller."""
from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import (
    FakeAccountRepository,
    FakeCardAccountRepository,
    FakeCardRepository,
    FakeCustomerRepository,
)


@pytest.fixture
def payments_harness():
    async def _resolve_customer(repo):
        return await repo.create(
            identification_number=f"id-{uuid.uuid4().hex[:10]}", first_name="Ada", last_name="Lovelace",
            date_of_birth=date(1990, 1, 1), gender=None, auth0_sub="auth0|owner",
        )

    customers_repo = FakeCustomerRepository()
    owner = asyncio.run(_resolve_customer(customers_repo))
    customer_id = owner.id

    accounts = FakeAccountRepository(known_customers={customer_id})
    h = build(accounts=accounts)
    h.customers.rows[owner.id] = owner
    with h.client:
        account_response = h.client.post(
            "/accounts", json={"currency": "USD", "customer_id": str(customer_id)}
        )
    paying_account = accounts.rows[account_response.json()["account_number"]]

    card_accounts = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account.id})
    cards = FakeCardRepository()
    h2 = build(accounts=accounts, card_accounts=card_accounts, cards=cards)
    h2.client.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "auth0|test",
        "permissions": ["write:admin"],
    }
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
    payload = {"amount": 20000, "source_account": h.paying_account.account_number}
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


def test_customer_can_pay_from_a_second_account_they_own(payments_harness):
    """The whole point of this change: the customer picks which of their own
    accounts pays the card, not just the one fixed at issuance."""
    h = payments_harness
    # `POST /accounts` requires write:admin, which this harness's overridden
    # (plain customer) identity doesn't have — seed the second account
    # directly on the repository instead, the same way the fixture itself
    # resolves the owning customer.
    second_account = asyncio.run(
        h.accounts.create(currency="USD", customer_id=h.customer_id)
    )

    issued = _issue(h).json()
    card_account_id = issued["card_account"]["id"]

    response = _pay(h, card_account_id, source_account=second_account.account_number)

    assert response.status_code == 202
    _, key, value = h.publisher.published[0]
    assert key == second_account.account_number
    assert value["account_id"] == second_account.account_number


def test_paying_from_an_account_owned_by_another_customer_is_forbidden(payments_harness):
    h = payments_harness
    stranger_customer_id = uuid.uuid4()
    h.accounts.known_customers.add(stranger_customer_id)
    stranger_account = asyncio.run(
        h.accounts.create(currency="USD", customer_id=stranger_customer_id)
    )

    issued = _issue(h).json()
    card_account_id = issued["card_account"]["id"]

    response = _pay(h, card_account_id, source_account=stranger_account.account_number)

    assert response.status_code == 403
    assert len(h.publisher.published) == 0


def test_paying_from_an_unknown_account_number_returns_404(payments_harness):
    h = payments_harness
    issued = _issue(h).json()
    card_account_id = issued["card_account"]["id"]

    response = _pay(h, card_account_id, source_account="9999999999999999")

    assert response.status_code == 404
    assert len(h.publisher.published) == 0
