"""Customer <-> Auth0 identity linking (spec §1).

`CurrentCustomerDep` composes `CurrentUserDep` (an Auth0 access-token check)
with a lookup by `auth0_sub`. Tests override `get_current_user` directly per
the project convention — the real Auth0 verification is exercised nowhere in
this suite, only the composition around it.
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


# --- repository: get_by_auth0_sub -------------------------------------------


def test_get_by_auth0_sub_returns_the_matching_customer():
    async def scenario():
        h = build()
        repo = h.customers
        created = await repo.create(
            identification_number="ID-1", first_name="A", last_name="B",
            date_of_birth="1990-01-01", gender=None,
        )
        await repo.update(created.id, auth0_sub="auth0|abc123")
        return await repo.get_by_auth0_sub("auth0|abc123"), created.id

    found, customer_id = asyncio.run(scenario())
    assert found is not None
    assert found.id == customer_id


def test_get_by_auth0_sub_returns_none_when_no_customer_matches():
    async def scenario():
        h = build()
        return await h.customers.get_by_auth0_sub("auth0|nobody")

    assert asyncio.run(scenario()) is None


# --- PATCH /customers/{id}/auth0-link ---------------------------------------


def test_patch_auth0_link_sets_the_sub_and_current_customer_resolves():
    h = build()
    with h.client:
        customer_id = _create_customer(h.client).json()["id"]

        response = h.client.patch(f"/customers/{customer_id}/auth0-link", json={"sub": "auth0|xyz"})

        assert response.status_code == 200
        assert response.json()["auth0_sub"] == "auth0|xyz"


# --- CurrentCustomerDep -------------------------------------------------


def test_current_customer_dep_401_when_no_token_override_present():
    h = build()
    with h.client:
        response = h.client.get("/customers/me")
        # No override for get_current_user -> Auth0FastAPI is unconfigured -> 503,
        # which is the documented degrade path (config/dependencies._require_auth0).
        assert response.status_code == 503


def test_current_customer_dep_404_for_a_valid_token_with_no_linked_customer():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|unknown"}
    with h.client:
        response = h.client.get("/customers/me")
        assert response.status_code == 404


def test_current_customer_dep_resolves_the_linked_customer():
    h = build()
    with h.client:
        customer_id = _create_customer(h.client).json()["id"]
        h.client.patch(f"/customers/{customer_id}/auth0-link", json={"sub": "auth0|linked"})
        h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|linked"}

        response = h.client.get("/customers/me")

        assert response.status_code == 200
        assert response.json()["id"] == customer_id
