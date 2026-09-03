"""Customer endpoints — soft delete and the accounts-must-be-empty rule.

"Empty" means every account is either not active (blocked/closed) or sits at
a zero balance — not that the customer has no account rows at all.
"""
from __future__ import annotations

import asyncio
import uuid

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build


def _create_customer(client, identification_number: str = "ID-001"):
    return client.post(
        "/customers",
        json={
            "identification_number": identification_number,
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": "1990-01-15",
        },
    )


def _open_account(h, customer_id: uuid.UUID) -> str:
    branch_id = uuid.uuid4()
    h.accounts.known_customers.add(customer_id)
    h.accounts.known_branches.add(branch_id)
    created = h.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(customer_id), "branch_id": str(branch_id)},
    )
    assert created.status_code == 201
    return created.json()["account_number"]


def test_soft_delete_deactivates_a_customer_with_no_accounts():
    h = build()
    with h.client:
        customer_id = _create_customer(h.client).json()["id"]

        response = h.client.delete(f"/customers/{customer_id}")

        assert response.status_code == 200
        assert response.json()["active"] is False


def test_soft_delete_deactivates_a_customer_whose_only_account_has_a_zero_balance():
    h = build()
    with h.client:
        customer_id = uuid.UUID(_create_customer(h.client).json()["id"])
        _open_account(h, customer_id)  # new accounts always start at 0

        response = h.client.delete(f"/customers/{customer_id}")

        assert response.status_code == 200
        assert response.json()["active"] is False


def test_soft_delete_deactivates_a_customer_whose_funded_account_was_closed():
    h = build()
    with h.client:
        customer_id = uuid.UUID(_create_customer(h.client).json()["id"])
        account_number = _open_account(h, customer_id)
        asyncio.run(h.accounts.apply_balance(account_number, 5_000))
        closed = h.client.delete(f"/accounts/{account_number}")
        assert closed.status_code == 200

        response = h.client.delete(f"/customers/{customer_id}")

        assert response.status_code == 200
        assert response.json()["active"] is False


def test_soft_delete_is_refused_while_an_active_account_still_carries_a_balance():
    h = build()
    with h.client:
        customer_id = uuid.UUID(_create_customer(h.client).json()["id"])
        account_number = _open_account(h, customer_id)
        asyncio.run(h.accounts.apply_balance(account_number, 5_000))

        response = h.client.delete(f"/customers/{customer_id}")

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "CustomerAccountsNotEmptyError"
        # The refusal must not have side-effected the row.
        assert h.customers.rows[customer_id].active is True


def test_soft_delete_a_nonexistent_customer_is_a_clean_404():
    h = build()
    with h.client:
        response = h.client.delete(f"/customers/{uuid.uuid4()}")
        assert response.status_code == 404


# --- CurrentUserDep guard: GET /customers/{customer_id} ---------------------
# Backs the transfer recipient-preview lookup (find-recipient.ts), which
# resolves a recipient's name after resolving their account — so this route
# must accept any authenticated caller, not just the customer's own record.


def test_get_by_customer_id_requires_auth():
    h = build()
    with h.client:
        customer_id = _create_customer(h.client, "ID-AUTH-001").json()["id"]
        # No override for get_current_user -> Auth0FastAPI is unconfigured ->
        # 503, the documented degrade path (config/dependencies._require_auth0).
        response = h.client.get(f"/customers/{customer_id}")
        assert response.status_code == 503


def test_get_by_customer_id_resolves_for_any_authenticated_caller():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|someone-else"}
    with h.client:
        customer_id = _create_customer(h.client, "ID-AUTH-002").json()["id"]
        response = h.client.get(f"/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["id"] == customer_id


def test_get_by_customer_id_unknown_is_404():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|someone-else"}
    with h.client:
        response = h.client.get(f"/customers/{uuid.uuid4()}")
        assert response.status_code == 404
