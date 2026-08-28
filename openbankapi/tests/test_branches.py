"""Branch endpoints — soft delete and the no-active-accounts rule.

Unlike the customer rule, this one only looks at status: a branch can be
soft-deleted as soon as no account there is `active`, regardless of balance.
"""
from __future__ import annotations

import uuid

from openbankapi.tests.conftest import build


def _create_branch(h, code: str = "BR1"):
    location_id = uuid.uuid4()
    h.branches.known_locations.add(location_id)
    return h.client.post(
        "/branches", json={"code": code, "name": "Test Branch", "location_id": str(location_id)}
    )


def _open_account(h, branch_id: uuid.UUID) -> str:
    customer_id = uuid.uuid4()
    h.accounts.known_customers.add(customer_id)
    h.accounts.known_branches.add(branch_id)
    created = h.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(customer_id), "branch_id": str(branch_id)},
    )
    assert created.status_code == 201
    return created.json()["account_number"]


def test_soft_delete_deactivates_a_branch_with_no_accounts():
    h = build()
    with h.client:
        branch_id = _create_branch(h).json()["id"]

        response = h.client.delete(f"/branches/{branch_id}")

        assert response.status_code == 200
        assert response.json()["active"] is False


def test_soft_delete_deactivates_a_branch_whose_account_was_closed():
    h = build()
    with h.client:
        branch_id = uuid.UUID(_create_branch(h).json()["id"])
        account_number = _open_account(h, branch_id)
        closed = h.client.delete(f"/accounts/{account_number}")
        assert closed.status_code == 200

        response = h.client.delete(f"/branches/{branch_id}")

        assert response.status_code == 200
        assert response.json()["active"] is False


def test_soft_delete_is_refused_while_the_branch_has_an_active_account():
    h = build()
    with h.client:
        branch_id = uuid.UUID(_create_branch(h).json()["id"])
        _open_account(h, branch_id)

        response = h.client.delete(f"/branches/{branch_id}")

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "BranchHasActiveAccountsError"
        # The refusal must not have side-effected the row.
        assert h.branches.rows[branch_id].active is True


def test_soft_delete_a_nonexistent_branch_is_a_clean_404():
    h = build()
    with h.client:
        response = h.client.delete(f"/branches/{uuid.uuid4()}")
        assert response.status_code == 404
