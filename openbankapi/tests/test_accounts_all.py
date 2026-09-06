"""`GET /accounts/all` — cross-customer admin list (admin-role-authorization).

Unlike `GET /accounts` (customer-scoped via `CurrentCustomerDep`), this
endpoint is guarded by `ReadAdminDep` ONLY and pages the unfiltered
repository `list()`, so an admin sees rows across customers.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import HTTPException

from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.model import Account, AccountStatus
from openbankapi.tests.conftest import build


def _account(number: str, customer_id: uuid.UUID) -> Account:
    now = dt.datetime.now(dt.timezone.utc)
    return Account(
        id=uuid.uuid4(), account_number=number, currency="USD",
        customer_id=customer_id, branch_id=uuid.uuid4(), balance=0,
        status=AccountStatus.ACTIVE, created_at=now, updated_at=now,
    )


def _seed_two_customers(h):
    first, second = uuid.uuid4(), uuid.uuid4()
    h.accounts.rows["1111111111111111"] = _account("1111111111111111", first)
    h.accounts.rows["2222222222222222"] = _account("2222222222222222", second)


def test_all_returns_401_without_token():
    h = build()

    async def _raise():
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "error_description": "missing or invalid token"},
        )

    h.client.app.dependency_overrides[get_current_user] = _raise
    with h.client:
        resp = h.client.get("/accounts/all")
        assert resp.status_code == 401


def test_all_returns_403_without_read_admin():
    h = build()

    async def _claims():
        return {"sub": "auth0|plain", "permissions": []}

    h.client.app.dependency_overrides[get_current_user] = _claims
    with h.client:
        resp = h.client.get("/accounts/all")
        assert resp.status_code == 403
        assert "read:admin" in str(resp.json())


def test_all_returns_rows_across_customers_with_read_admin():
    # Default harness claims carry read:admin for sub "test-admin", which has
    # NO linked Customer — proving the endpoint skips CurrentCustomerDep.
    h = build()
    _seed_two_customers(h)
    with h.client:
        resp = h.client.get("/accounts/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        numbers = {item["account_number"] for item in body["items"]}
        assert numbers == {"1111111111111111", "2222222222222222"}


def test_all_paginates():
    h = build()
    _seed_two_customers(h)
    with h.client:
        resp = h.client.get("/accounts/all?limit=1&offset=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert len(body["items"]) == 1
