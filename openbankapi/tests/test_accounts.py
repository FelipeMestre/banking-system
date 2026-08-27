"""Account endpoints — including the rule the whole architecture rests on."""
from __future__ import annotations

import uuid

import pytest

from openbankapi.api.v1.dtos.account_dto import AccountUpdateDTO
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository


def _create(wired):
    return wired.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(wired.customer_id),
              "branch_id": str(wired.branch_id)},
    )


# --- spec §11.1 -------------------------------------------------------------


def test_account_creation_returns_16_digits_and_zero_balance(wired):
    response = _create(wired)
    assert response.status_code == 201
    body = response.json()
    assert len(body["account_number"]) == 16
    assert body["account_number"].isdigit()
    assert body["balance"] == 0
    assert body["status"] == "active"


def test_the_client_cannot_choose_the_account_number(wired):
    """It is the Kafka partition key: correct by construction, not by validation."""
    response = wired.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(wired.customer_id),
              "branch_id": str(wired.branch_id),
              "account_number": "9999999999999999"},
    )
    assert response.status_code == 422


def test_a_generated_number_collision_never_surfaces_a_500():
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id},
                                   collide_times=2)
    h = build(accounts=accounts)
    with h.client:
        response = h.client.post(
            "/accounts",
            json={"currency": "USD", "customer_id": str(customer_id), "branch_id": str(branch_id)},
        )
    assert response.status_code == 201
    assert accounts.attempts == 3, "should have retried past both collisions"


# --- spec §11.3: balance is not writable --------------------------------------


def test_the_update_dto_has_no_balance_field_at_all():
    """Structural, not behavioural: the field must not exist to be set."""
    assert "balance" not in AccountUpdateDTO.model_fields


def test_sending_balance_in_an_update_is_rejected(wired):
    account_number = _create(wired).json()["account_number"]

    response = wired.client.put(f"/accounts/{account_number}", json={"balance": 999999})

    assert response.status_code == 422
    assert wired.client.get(f"/accounts/{account_number}").json()["balance"] == 0


def test_a_legitimate_update_still_leaves_the_balance_alone(wired):
    account_number = _create(wired).json()["account_number"]
    await_balance = wired.accounts.rows[account_number].balance

    response = wired.client.put(f"/accounts/{account_number}", json={"status": "blocked"})

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["balance"] == await_balance


# --- spec §11.4: referential integrity --------------------------------------


def test_a_nonexistent_customer_is_a_clean_4xx_not_a_db_error(wired):
    response = wired.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(uuid.uuid4()),
              "branch_id": str(wired.branch_id)},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ReferencedEntityNotFoundError"


def test_a_nonexistent_branch_is_a_clean_4xx(wired):
    response = wired.client.post(
        "/accounts",
        json={"currency": "USD", "customer_id": str(wired.customer_id),
              "branch_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422


# --- soft delete ------------------------------------------------------------


def test_deleting_an_account_closes_it_rather_than_removing_it(wired):
    account_number = _create(wired).json()["account_number"]

    assert wired.client.delete(f"/accounts/{account_number}").json()["status"] == "closed"
    assert wired.client.get(f"/accounts/{account_number}").status_code == 200


def test_an_unknown_account_is_404(wired):
    assert wired.client.get("/accounts/1111111111111111").status_code == 404
