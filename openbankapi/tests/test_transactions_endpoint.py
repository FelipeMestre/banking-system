"""`GET /accounts/{account_number}/transactions` (spec §3.3, §3.4) and the
customer-scoping of `GET /accounts` (spec §2.1).
"""
from __future__ import annotations

import datetime as dt
import uuid

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository, FakeTransactionRepository

ACCOUNT_NUMBER = "1111111111111111"
OTHER_ACCOUNT_NUMBER = "2222222222222222"


def _ts(offset_seconds: int = 0) -> dt.datetime:
    return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=offset_seconds)


def _linked_customer(h, sub: str = "auth0|owner"):
    body = h.client.post(
        "/customers",
        json={
            "identification_number": f"ID-{uuid.uuid4().hex[:12]}", "first_name": "A", "last_name": "B",
            "date_of_birth": "1990-01-01",
        },
    ).json()
    customer_id = uuid.UUID(body["id"])
    h.client.patch(f"/customers/{customer_id}/auth0-link", json={"sub": sub})
    return customer_id


def _as(h, sub: str):
    h.client.app.dependency_overrides[get_current_user] = lambda: {
        "sub": sub,
        "permissions": ["read:admin", "write:admin"],
        "scope": "read:admin write:admin",
    }


def _as_read(h, sub: str):
    h.client.app.dependency_overrides[get_current_user] = lambda: {
        "sub": sub,
        "permissions": ["read:admin"],
        "scope": "read:admin",
    }


def _harness_with_two_customers_and_accounts():
    branch_id = uuid.uuid4()
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={owner_id, other_id}, known_branches={branch_id})
    h = build(accounts=accounts)
    with h.client:
        owner_customer_id = _linked_customer(h, "auth0|owner")
        other_customer_id = _linked_customer(h, "auth0|other")
        # Rebuild the fake with real customer ids as owners (the earlier
        # `known_customers` ids were placeholders only used to pass FK checks).
        h.accounts.known_customers |= {owner_customer_id, other_customer_id}
        owner_account = h.client.post(
            "/accounts",
            json={"currency": "USD", "customer_id": str(owner_customer_id), "branch_id": str(branch_id)},
        ).json()
        other_account = h.client.post(
            "/accounts",
            json={"currency": "USD", "customer_id": str(other_customer_id), "branch_id": str(branch_id)},
        ).json()
        yield h, owner_account["account_number"], other_account["account_number"]


# --- authorization ------------------------------------------------------------


def test_customer_cannot_access_another_customers_account_transactions():
    for h, owner_account, other_account in _harness_with_two_customers_and_accounts():
        _as(h, "auth0|owner")
        response = h.client.get(f"/accounts/{other_account}/transactions")
        assert response.status_code == 403


def test_customer_can_access_their_own_accounts_transactions():
    for h, owner_account, other_account in _harness_with_two_customers_and_accounts():
        _as(h, "auth0|owner")
        response = h.client.get(f"/accounts/{owner_account}/transactions")
        assert response.status_code == 200


# --- pagination -----------------------------------------------------------------


def test_an_account_with_no_transactions_returns_an_empty_page():
    for h, owner_account, _ in _harness_with_two_customers_and_accounts():
        _as(h, "auth0|owner")
        response = h.client.get(f"/accounts/{owner_account}/transactions")
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}


def test_no_cursor_returns_the_first_page_newest_first():
    for h, owner_account, _ in _harness_with_two_customers_and_accounts():
        for i in range(3):
            h.transactions.rows.append(_row(owner_account, i))
        _as(h, "auth0|owner")
        response = h.client.get(f"/accounts/{owner_account}/transactions?limit=2")
        body = response.json()
        assert [t["amount"] for t in body["items"]] == [2, 1]
        assert body["next_cursor"] is not None


def test_walking_all_pages_with_the_cursor_visits_every_row_once():
    for h, owner_account, _ in _harness_with_two_customers_and_accounts():
        for i in range(5):
            h.transactions.rows.append(_row(owner_account, i))
        _as(h, "auth0|owner")
        seen = []
        params = {"limit": 2}
        for _ in range(10):
            response = h.client.get(f"/accounts/{owner_account}/transactions", params=params)
            body = response.json()
            seen.extend(t["amount"] for t in body["items"])
            if body["next_cursor"] is None:
                break
            params = {"limit": 2, "cursor": body["next_cursor"]}
        assert seen == [4, 3, 2, 1, 0]


def _row(account_number: str, amount: int):
    from openbankapi.domain.model import Transaction, TransactionType

    return Transaction(
        id=uuid.uuid4(), request_id=uuid.uuid4(), account_number=account_number,
        type=TransactionType.CREDIT, amount=amount, counterparty_account=OTHER_ACCOUNT_NUMBER,
        decline_reason=None, ts=_ts(amount),
    )


# --- accounts list scoping (spec §2.1) -----------------------------------------


def test_get_accounts_only_returns_the_current_customers_own_accounts():
    for h, owner_account, other_account in _harness_with_two_customers_and_accounts():
        _as(h, "auth0|owner")
        response = h.client.get("/accounts")
        numbers = {a["account_number"] for a in response.json()["items"]}
        assert numbers == {owner_account}


def test_get_accounts_is_an_empty_list_for_a_customer_with_no_accounts():
    h = build()
    with h.client:
        customer_id = _linked_customer(h, "auth0|lonely")
        _as(h, "auth0|lonely")
        response = h.client.get("/accounts")
        assert response.status_code == 200
        assert response.json()["items"] == []


def test_get_accounts_requires_a_resolved_customer():
    h = build(with_admin=False)
    with h.client:
        response = h.client.get("/accounts")
        assert response.status_code == 503  # unconfigured Auth0 -> documented degrade path
