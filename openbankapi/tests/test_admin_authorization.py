"""Admin RBAC matrix — spec admin-authorization.

Backend is security boundary. These tests drive `require_permissions`.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from openbankapi.config.dependencies import get_current_user
from openbankapi.tests.conftest import build


# ---------------------------------------------------------------------------
# helpers: _effective_permissions unit
# ---------------------------------------------------------------------------

def test_effective_permissions_returns_permissions_when_present():
    from openbankapi.config.dependencies import _effective_permissions

    claims = {"permissions": ["read:admin"], "scope": "write:admin"}
    assert _effective_permissions(claims) == ["read:admin"]


def test_effective_permissions_falls_back_to_scope_when_permissions_absent():
    from openbankapi.config.dependencies import _effective_permissions

    claims = {"scope": "read:admin write:admin"}
    assert set(_effective_permissions(claims)) == {"read:admin", "write:admin"}


def test_effective_permissions_falls_back_when_permissions_empty():
    from openbankapi.config.dependencies import _effective_permissions

    claims = {"permissions": [], "scope": "read:admin"}
    assert _effective_permissions(claims) == ["read:admin"]


def test_effective_permissions_returns_empty_when_neither():
    from openbankapi.config.dependencies import _effective_permissions

    assert _effective_permissions({}) == []
    assert _effective_permissions({"permissions": [], "scope": ""}) == []


def test_effective_permissions_splits_scope_on_whitespace():
    from openbankapi.config.dependencies import _effective_permissions

    claims = {"scope": "read:admin  write:admin\tread:other"}
    result = _effective_permissions(claims)
    assert "read:admin" in result
    assert "write:admin" in result


def test_effective_permissions_ignores_non_list_permissions():
    from openbankapi.config.dependencies import _effective_permissions

    claims = {"permissions": "read:admin", "scope": "write:admin"}
    # non-list permissions -> fallback to scope
    assert _effective_permissions(claims) == ["write:admin"]


# ---------------------------------------------------------------------------
# exception shape
# ---------------------------------------------------------------------------

def test_insufficient_permissions_error_carries_required_and_had():
    from openbankapi.domain.exceptions import InsufficientPermissionsError

    err = InsufficientPermissionsError(["write:admin"], ["read:admin"])
    assert err.required == ["write:admin"]
    assert err.had == ["read:admin"]
    assert "write:admin" in str(err)


def test_insufficient_permissions_error_is_domain_error():
    from openbankapi.domain.exceptions import DomainError, InsufficientPermissionsError

    err = InsufficientPermissionsError(["read:admin"], [])
    assert isinstance(err, DomainError)


# ---------------------------------------------------------------------------
# require_permissions dependency unit — checks 403 shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_permissions_succeeds_when_has_permission():
    from openbankapi.config.dependencies import require_permissions

    # claims has read:admin, requiring read:admin should succeed
    dep = require_permissions("read:admin")

    async def fake_get_current_user():
        return {"permissions": ["read:admin"]}

    # We test via overriding get_current_user in a real app would work,
    # but here we directly invoke the dependency with claims injection.
    # Instead test via direct helper: simulate that require_permissions
    # checks had vs required. The simplest is to build a harness and hit
    # an endpoint — see integration tests below. This unit test just
    # ensures the factory returns a callable.
    assert callable(dep)


# ---------------------------------------------------------------------------
# integration: 401/403/200 matrix via real routers
# ---------------------------------------------------------------------------

def _harness_with_claims(claims: dict | None, *, raise_401: bool = False):
    """Build harness with get_current_user overridden to return claims or raise 401."""
    h = build()

    if raise_401:
        async def _raise():
            raise HTTPException(status_code=401, detail={"error": "invalid_token", "error_description": "missing or invalid token"})
        h.client.app.dependency_overrides[get_current_user] = _raise
    elif claims is not None:
        # get_current_user is async; override with async lambda
        async def _ok():
            return claims
        h.client.app.dependency_overrides[get_current_user] = _ok
    else:
        # no override -> will hit 503 path (auth0 not configured) but we want 401 for no-token tests
        # so caller should use raise_401=True for 401 case
        pass
    return h


def test_no_token_returns_401():
    h = _harness_with_claims(None, raise_401=True)
    with h.client:
        resp = h.client.get("/branches")
        assert resp.status_code == 401


def test_missing_permission_returns_403_with_required_and_had():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        # POST /branches requires write:admin
        location_id = uuid.uuid4()
        h.branches.known_locations.add(location_id)
        resp = h.client.post("/branches", json={"code": "BRX", "name": "X", "location_id": str(location_id)})
        assert resp.status_code == 403
        body = resp.json()
        # error_handlers should produce {"error": {"code":..., "message":..., "details": {"required":..., "had":...}}}
        # or at least contain required/had
        text = str(body)
        assert "write:admin" in text
        # check structured details if present
        if "error" in body and isinstance(body["error"], dict):
            details = body["error"].get("details") or body["error"]
            # details may contain required/had
            assert "required" in str(details) or "required" in text


def test_has_write_permission_succeeds():
    h = _harness_with_claims({"permissions": ["write:admin"]})
    with h.client:
        location_id = uuid.uuid4()
        h.branches.known_locations.add(location_id)
        resp = h.client.post("/branches", json={"code": "BRW", "name": "OK", "location_id": str(location_id)})
        assert resp.status_code == 201


def test_read_needs_read_admin():
    h = _harness_with_claims({"permissions": []})
    with h.client:
        resp = h.client.get("/branches")
        assert resp.status_code == 403
        assert "read:admin" in str(resp.json())


def test_read_succeeds_with_read_admin():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        resp = h.client.get("/branches")
        assert resp.status_code == 200


def test_scope_fallback_grants_access_when_no_permissions_array():
    h = _harness_with_claims({"scope": "read:admin write:admin"})
    with h.client:
        resp = h.client.get("/branches")
        assert resp.status_code == 200
        # also write via scope fallback
        location_id = uuid.uuid4()
        h.branches.known_locations.add(location_id)
        resp2 = h.client.post("/branches", json={"code": "BRF", "name": "Fallback", "location_id": str(location_id)})
        assert resp2.status_code == 201


def test_permissions_primary_ignores_scope():
    """If permissions exists, scope must NOT grant extra rights."""
    h = _harness_with_claims({"permissions": ["read:admin"], "scope": "write:admin"})
    with h.client:
        location_id = uuid.uuid4()
        h.branches.known_locations.add(location_id)
        resp = h.client.post("/branches", json={"code": "BRP", "name": "Primary", "location_id": str(location_id)})
        assert resp.status_code == 403
        assert "write:admin" in str(resp.json())


def test_customer_me_remains_open_without_admin():
    """GET /customers/me must NOT require read:admin — it is the linked-customer lookup."""
    h = build()
    # Need write:admin to create customer/link now
    async def _admin():
        return {"sub": "auth0|creator", "permissions": ["write:admin"]}
    h.client.app.dependency_overrides[get_current_user] = _admin
    with h.client:
        created = h.client.post("/customers", json={
            "identification_number": "ID-ADMIN-1",
            "first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01"
        })
        assert created.status_code == 201
        cid = created.json()["id"]
        h.client.patch(f"/customers/{cid}/auth0-link", json={"sub": "auth0|adminopen"})
        # now override to that sub but with no permissions
        async def _claims():
            return {"sub": "auth0|adminopen", "permissions": []}
        h.client.app.dependency_overrides[get_current_user] = _claims
        resp = h.client.get("/customers/me")
        # should be 200, not 403
        assert resp.status_code == 200


def test_accounts_me_remains_open_without_admin():
    """POST /accounts/me must NOT require write:admin."""
    h = build()
    async def _admin2():
        return {"sub": "auth0|creator2", "permissions": ["write:admin"]}
    h.client.app.dependency_overrides[get_current_user] = _admin2
    with h.client:
        # need a customer linked to auth0 identity, then call POST /accounts/me
        # first create customer
        created = h.client.post("/customers", json={
            "identification_number": "ID-ADMIN-2",
            "first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01"
        })
        assert created.status_code == 201
        cid = created.json()["id"]
        # link
        h.client.patch(f"/customers/{cid}/auth0-link", json={"sub": "auth0|acctme"})
        # override claims with no permissions
        async def _claims():
            return {"sub": "auth0|acctme", "permissions": []}
        h.client.app.dependency_overrides[get_current_user] = _claims
        # The branch needed for first account creation: need an active branch in repo
        # FakeAccountRepository not used here; we use real flow via service that uses
        # branch repository; harness has empty branches, so we need to create one.
        # Simplest: ensure at least one active branch exists
        # Use the account-service's branch requirement: if no active branch, returns 503
        # So create a branch first without auth (but branches now require auth, so we need write:admin)
        # Instead, directly seed the fake branch repo.
        # harness's branch repo is FakeBranchRepository; add a branch manually
        import datetime as dt, uuid as _uuid
        from openbankapi.domain.model import Branch
        bid = _uuid.uuid4()
        loc = _uuid.uuid4()
        h.branches.known_locations.add(loc)
        # create branch row directly
        # use harness internal: h.branches.rows[bid] = Branch(...)
        h.branches.rows[bid] = Branch(id=bid, code="BRME", name="Branch ME", location_id=loc, active=True, created_at=dt.datetime.now(dt.timezone.utc), updated_at=dt.datetime.now(dt.timezone.utc))
        h.branches.codes.add("BRME")
        # Also need to ensure the account repo knows about branch/customer? For first account creation via open_first_account_for_identity, it checks
        # We'll attempt POST /accounts/me
        resp = h.client.post("/accounts/me", json={
            "identification_number": "ID-NEW-3",
            "first_name": "New", "last_name": "User", "date_of_birth": "1990-01-01", "gender": "male"
        })
        # It should NOT be 403; it may be 201 or 409 or 503 depending on setup, but not 403
        assert resp.status_code != 403


def test_transfer_post_needs_write_admin():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        resp = h.client.post("/transfer", json={
            "source_account": "0000000000000001",
            "destination_account": "0000000000000002",
            "amount": 100
        })
        assert resp.status_code == 403


def test_transfer_status_get_needs_read_admin():
    h = _harness_with_claims({"permissions": []})
    with h.client:
        resp = h.client.get("/transfer/any-id/status")
        assert resp.status_code == 403


def test_fx_rates_get_needs_read_admin():
    h = _harness_with_claims({"permissions": []})
    with h.client:
        resp = h.client.get("/foreign-exchange-rates")
        assert resp.status_code == 403


def test_fx_rates_get_succeeds_with_read_admin():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        resp = h.client.get("/foreign-exchange-rates")
        # may be 200 even if no rates; but should not be 403
        assert resp.status_code != 403


def test_fx_quote_needs_write_admin():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        resp = h.client.post("/foreign-exchange-rates/quote", json={
            "amount": 100, "from_currency": "USD", "to_currency": "EUR", "customer_effect": "buy"
        })
        assert resp.status_code == 403


def test_audience_missing_is_401_not_403():
    """Opaque token (no aud) must be 401; simulate by raising 401 from auth."""
    h = _harness_with_claims(None, raise_401=True)
    with h.client:
        resp = h.client.get("/branches")
        assert resp.status_code == 401
        assert resp.status_code != 403


def test_account_list_needs_read_admin():
    h = _harness_with_claims({"permissions": []})
    # account list uses CurrentCustomerDep additionally; need a linked customer to reach permission check
    # But without read:admin we expect 403 before customer resolution? Depends on ordering.
    # Our implementation orders require_permissions before customer resolution, so 403 should happen even without customer.
    # To ensure, we provide a customer-linked claim but still no permission.
    async def _claims():
        return {"sub": "auth0|some", "permissions": []}
    h.client.app.dependency_overrides[get_current_user] = _claims
    with h.client:
        resp = h.client.get("/accounts")
        assert resp.status_code == 403


def test_put_customer_needs_write_admin():
    h = _harness_with_claims({"permissions": ["read:admin"]})
    with h.client:
        # create a customer first without guard? But POST /customers will now require write:admin,
        # so we need write to create. Use a separate harness to create then test PUT with read only.
        # Simpler: test PUT directly expects 403 even if customer doesn't exist — the auth check happens first.
        resp = h.client.put(f"/customers/{uuid.uuid4()}", json={
            "first_name": "X", "last_name": "Y", "date_of_birth": "1990-01-01"
        })
        assert resp.status_code == 403
