"""First-account self-service creation (`POST /accounts/me`).

Covers the whole stack per the design's single-file convention: the two new
repository-port methods (via fakes), the two new domain exceptions and their
HTTP mapping, `AccountService.open_first_account` orchestration, and the
`TestClient` scenarios for the new endpoint. Mirrors `test_customer_auth_link.py`'s
style — real fakes and `dependency_overrides`, never a mocked repository.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from fastapi import HTTPException

from openbankapi.api.v1.services.error_handlers import status_for
from openbankapi.config import Settings
from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.exceptions import (
    CustomerAlreadyHasAccountError,
    DuplicateError,
    NoActiveBranchAvailableError,
)
from openbankapi.domain.model import Branch
from openbankapi.domain.service.account_service import AccountService
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import (
    FakeAccountRepository,
    FakeBranchRepository,
    FakeCustomerRepository,
    FakePublisher,
)


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


def _link_current_customer(h, sub: str = "auth0|first-account"):
    customer_id = _create_customer(h.client).json()["id"]
    h.client.patch(f"/customers/{customer_id}/auth0-link", json={"sub": sub})
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": sub}
    return customer_id


def _create_active_branch(h) -> str:
    location_id = h.client.post("/locations", json={"name": "HQ"}).json()["id"]
    h.branches.known_locations.add(uuid.UUID(location_id))
    branch = h.client.post(
        "/branches", json={"code": "B1", "name": "Main", "location_id": location_id}
    ).json()
    return branch["id"]


# --- Phase 1.1 / 2.1: repository port contract checks (via fakes) ----------


def test_fake_account_repository_exposes_the_new_guard_methods():
    async def scenario():
        repo = FakeAccountRepository()
        customer_id = uuid.uuid4()
        await repo.lock_customer_for_account_creation(customer_id)
        return await repo.has_any_account_for_customer(customer_id)

    assert asyncio.run(scenario()) is False


def test_account_repository_exposes_lock_identity_for_account_creation():
    """Amendment: a second lock, re-keyed on `auth0_sub`, for the
    never-linked-identity path — alongside, not replacing, the
    customer_id-keyed lock the already-shipped branch still uses."""

    async def scenario():
        repo = FakeAccountRepository()
        await repo.lock_identity_for_account_creation("auth0|new-identity")
        return True

    assert asyncio.run(scenario()) is True


def test_fake_branch_repository_exposes_get_oldest_active():
    async def scenario():
        repo = FakeBranchRepository()
        return await repo.get_oldest_active()

    assert asyncio.run(scenario()) is None


# --- Phase 2.1: has_any_account_for_customer / get_oldest_active behavior --


def test_has_any_account_for_customer_true_after_any_account_exists():
    async def scenario():
        customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
        before = await repo.has_any_account_for_customer(customer_id)
        await repo.create(currency="USD", customer_id=customer_id, branch_id=branch_id)
        after = await repo.has_any_account_for_customer(customer_id)
        return before, after

    before, after = asyncio.run(scenario())
    assert before is False
    assert after is True


def test_has_any_account_for_customer_true_even_when_only_account_is_closed():
    async def scenario():
        customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
        account = await repo.create(currency="USD", customer_id=customer_id, branch_id=branch_id)
        await repo.close(account.account_number)
        return await repo.has_any_account_for_customer(customer_id)

    assert asyncio.run(scenario()) is True


def test_get_oldest_active_picks_earliest_created_at_and_ignores_inactive():
    async def scenario():
        repo = FakeBranchRepository()
        oldest = Branch(
            id=uuid.uuid4(), code="OLD", name="Oldest", location_id=uuid.uuid4(), active=True,
            created_at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
            updated_at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
        )
        newer_active = Branch(
            id=uuid.uuid4(), code="NEW", name="Newer", location_id=uuid.uuid4(), active=True,
            created_at=dt.datetime(2021, 1, 1, tzinfo=dt.timezone.utc),
            updated_at=dt.datetime(2021, 1, 1, tzinfo=dt.timezone.utc),
        )
        older_inactive = Branch(
            id=uuid.uuid4(), code="INA", name="Inactive", location_id=uuid.uuid4(), active=False,
            created_at=dt.datetime(2019, 1, 1, tzinfo=dt.timezone.utc),
            updated_at=dt.datetime(2019, 1, 1, tzinfo=dt.timezone.utc),
        )
        repo.rows[older_inactive.id] = older_inactive
        repo.rows[newer_active.id] = newer_active
        repo.rows[oldest.id] = oldest
        return await repo.get_oldest_active()

    found = asyncio.run(scenario())
    assert found is not None
    assert found.code == "OLD"


def test_get_oldest_active_returns_none_when_no_branch_is_active():
    async def scenario():
        repo = FakeBranchRepository()
        return await repo.get_oldest_active()

    assert asyncio.run(scenario()) is None


# --- Phase 1.5: exception -> HTTP status mapping ----------------------------


def test_customer_already_has_account_error_maps_to_409():
    assert status_for(CustomerAlreadyHasAccountError(uuid.uuid4())) == 409


def test_no_active_branch_available_error_maps_to_503():
    assert status_for(NoActiveBranchAvailableError()) == 503


# --- Phase 2.4: AccountService.open_first_account ---------------------------


def _build_service(*, accounts=None, branches=None):
    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    return AccountService(
        settings,
        accounts if accounts is not None else FakeAccountRepository(),
        FakePublisher(),
        branches if branches is not None else FakeBranchRepository(),
    )


def test_open_first_account_raises_409_when_customer_already_has_an_account():
    async def scenario():
        customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
        accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
        await accounts.create(currency="USD", customer_id=customer_id, branch_id=branch_id)
        branches = FakeBranchRepository()
        branches.rows[branch_id] = Branch(
            id=branch_id, code="B1", name="Main", location_id=uuid.uuid4(), active=True,
            created_at=dt.datetime.now(dt.timezone.utc),
            updated_at=dt.datetime.now(dt.timezone.utc),
        )
        service = _build_service(accounts=accounts, branches=branches)

        class _Customer:
            id = customer_id

        try:
            await service.open_first_account(_Customer())
            return False
        except CustomerAlreadyHasAccountError:
            return True

    assert asyncio.run(scenario()) is True


def test_open_first_account_raises_503_when_no_active_branch_exists():
    async def scenario():
        customer_id = uuid.uuid4()
        accounts = FakeAccountRepository(known_customers={customer_id})
        service = _build_service(accounts=accounts, branches=FakeBranchRepository())

        class _Customer:
            id = customer_id

        try:
            await service.open_first_account(_Customer())
            return False
        except NoActiveBranchAvailableError:
            return True

    assert asyncio.run(scenario()) is True


def test_open_first_account_creates_a_usd_account_at_the_resolved_branch():
    async def scenario():
        customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
        accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
        branches = FakeBranchRepository()
        branches.rows[branch_id] = Branch(
            id=branch_id, code="B1", name="Main", location_id=uuid.uuid4(), active=True,
            created_at=dt.datetime.now(dt.timezone.utc),
            updated_at=dt.datetime.now(dt.timezone.utc),
        )
        service = _build_service(accounts=accounts, branches=branches)

        class _Customer:
            id = customer_id

        return await service.open_first_account(_Customer())

    account = asyncio.run(scenario())
    assert account.currency == "USD"
    assert account.balance == 0


# --- Phase 10: AccountService.open_first_account_for_identity (amendment) --


def _build_service_for_identity(*, accounts=None, branches=None, customers=None):
    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    return AccountService(
        settings,
        accounts if accounts is not None else FakeAccountRepository(),
        FakePublisher(),
        branches if branches is not None else FakeBranchRepository(),
        customer_repository=customers if customers is not None else FakeCustomerRepository(),
    )


def _active_branch() -> tuple:
    branch_id = uuid.uuid4()
    branches = FakeBranchRepository()
    branches.rows[branch_id] = Branch(
        id=branch_id, code="B1", name="Main", location_id=uuid.uuid4(), active=True,
        created_at=dt.datetime.now(dt.timezone.utc), updated_at=dt.datetime.now(dt.timezone.utc),
    )
    return branches, branch_id


_VALID_KYC = {
    "identification_number": "ID-999",
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": dt.date(1990, 1, 1),
    "gender": None,
}


def _open_for_identity(service, sub: str, kyc: dict):
    return service.open_first_account_for_identity(sub, **kyc)


class _AnyCustomerIsKnown:
    """`FakeAccountRepository`'s FK simulation needs the customer_id
    pre-registered in `known_customers` — but a never-linked identity's
    `Customer` row is created dynamically inside this same call, so there is
    no id to register up front. A real Postgres FK has no such problem (the
    row already exists by the time the account insert runs); this stands in
    for "any id created by this call is fine", matching that reality."""

    def __contains__(self, _item) -> bool:
        return True


def test_open_first_account_for_identity_creates_customer_and_account_atomically():
    async def scenario():
        branches, branch_id = _active_branch()
        accounts = FakeAccountRepository(known_customers=_AnyCustomerIsKnown(), known_branches={branch_id})
        customers = FakeCustomerRepository()
        service = _build_service_for_identity(accounts=accounts, branches=branches, customers=customers)

        account = await _open_for_identity(service, "auth0|new", _VALID_KYC)
        return account, customers, accounts

    account, customers, accounts = asyncio.run(scenario())
    assert account.currency == "USD"
    assert len(customers.rows) == 1
    created_customer = next(iter(customers.rows.values()))
    assert created_customer.auth0_sub == "auth0|new"
    assert account.customer_id == created_customer.id


# 422-on-missing-field and 422-on-underage are exercised at the router/endpoint
# level (Phase 11 below): validation happens in the router against the strict
# `FirstAccountKycDTO`, BEFORE this pure domain method is ever called, so the
# service never sees an incomplete or underage payload (keeps the domain
# layer free of any api-layer/Pydantic import, per this codebase's layering
# rule — see the deviation note in apply-progress).


class _AlwaysMissingThenDuplicateCustomerRepository(FakeCustomerRepository):
    """Simulates a genuinely lost race that the lock-then-recheck cannot
    catch: every `get_by_auth0_sub` lookup (both the initial one and the
    post-lock re-check) still returns None — as if the concurrent winner's
    write is not yet visible to this repository's reads — but `create()`
    still hits the real UNIQUE(auth0_sub) constraint and raises
    `DuplicateError`, exactly as `translate()` would (amendment: this is the
    documented final line of defense, spec's "Concurrency safety" requirement)."""

    async def get_by_auth0_sub(self, sub: str):
        return None

    async def create(self, **kwargs):
        raise DuplicateError("auth0_sub", kwargs.get("auth0_sub"))


def test_open_first_account_for_identity_lost_race_becomes_a_clean_409_not_a_500():
    async def scenario():
        branches, branch_id = _active_branch()
        accounts = FakeAccountRepository(known_branches={branch_id})
        customers = _AlwaysMissingThenDuplicateCustomerRepository()
        service = _build_service_for_identity(accounts=accounts, branches=branches, customers=customers)

        try:
            await _open_for_identity(service, "auth0|new", _VALID_KYC)
            return "no error"
        except DuplicateError as error:
            return "duplicate", error.field

    outcome = asyncio.run(scenario())
    assert outcome == ("duplicate", "auth0_sub")


# --- Phase 3.1 / 3.3: POST /accounts/me endpoint ----------------------------


def test_post_accounts_me_503_without_a_token_override_present():
    h = build()
    with h.client:
        # No override for get_current_user -> Auth0FastAPI is unconfigured -> 503,
        # the same documented degrade path used by test_customer_auth_link.py.
        response = h.client.post("/accounts/me")
        assert response.status_code == 503


def test_post_accounts_me_422_for_a_never_linked_identity_with_no_kyc_body():
    """MODIFIED (amendment): a never-linked identity used to 404 immediately
    via `CurrentCustomerDep`. Now the endpoint runs under `CurrentUserDep` and
    tries to auto-link — an empty body is simply missing every required KYC
    field, so it is a 422, not a 404."""
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|unknown"}
    with h.client:
        response = h.client.post("/accounts/me")
        assert response.status_code == 422


def test_post_accounts_me_201_auto_links_a_never_before_seen_identity_with_full_kyc():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|brand-new"}
    h.accounts.known_customers = _AnyCustomerIsKnown()
    with h.client:
        branch_id = _create_active_branch(h)
        h.accounts.known_branches.add(uuid.UUID(branch_id))

        response = h.client.post(
            "/accounts/me",
            json={
                "identification_number": "ID-777",
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "1990-01-15",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["currency"] == "USD"
        assert body["balance"] == 0
        assert len(h.customers.rows) == 1
        created_customer = next(iter(h.customers.rows.values()))
        assert created_customer.auth0_sub == "auth0|brand-new"


def test_post_accounts_me_422_for_a_never_linked_identity_missing_a_required_kyc_field():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|incomplete"}
    with h.client:
        _create_active_branch(h)

        response = h.client.post(
            "/accounts/me",
            json={"identification_number": "ID-777", "first_name": "Jane", "last_name": "Doe"},
        )

        assert response.status_code == 422
        assert len(h.customers.rows) == 0


def test_post_accounts_me_422_for_a_never_linked_identity_that_is_underage():
    h = build()
    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|underage"}
    with h.client:
        _create_active_branch(h)
        underage_dob = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=365 * 10)).isoformat()

        response = h.client.post(
            "/accounts/me",
            json={
                "identification_number": "ID-777",
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": underage_dob,
            },
        )

        assert response.status_code == 422
        assert len(h.customers.rows) == 0


def test_post_accounts_me_201_ignores_kyc_body_for_an_already_linked_customer():
    """Regression: a linked Customer's own data must never be overwritten by
    a KYC body sent along for the ride (spec — "Linked customer, KYC body
    ignored")."""
    h = build()
    with h.client:
        branch_id = _create_active_branch(h)
        customer_id = _link_current_customer(h)
        h.accounts.known_customers.add(uuid.UUID(customer_id))
        h.accounts.known_branches.add(uuid.UUID(branch_id))
        original = h.customers.rows[uuid.UUID(customer_id)]

        response = h.client.post(
            "/accounts/me",
            json={
                "identification_number": "SOMETHING-ELSE",
                "first_name": "Someone",
                "last_name": "Else",
                "date_of_birth": "2001-01-01",
            },
        )

        assert response.status_code == 201
        unchanged = h.customers.rows[uuid.UUID(customer_id)]
        assert unchanged.identification_number == original.identification_number
        assert unchanged.first_name == original.first_name
        assert unchanged.last_name == original.last_name


def test_post_accounts_me_401_unauthenticated_creates_nothing():
    """An invalid/missing token must never reach the auto-link branch."""
    h = build()

    def _reject():
        raise HTTPException(status_code=401, detail="invalid token")

    h.client.app.dependency_overrides[get_current_user] = _reject
    with h.client:
        response = h.client.post("/accounts/me")
        assert response.status_code == 401
        assert len(h.customers.rows) == 0


def test_post_accounts_me_201_creates_a_usd_account_ignoring_client_params():
    h = build()
    with h.client:
        branch_id = _create_active_branch(h)
        customer_id = _link_current_customer(h)
        h.accounts.known_customers.add(uuid.UUID(customer_id))
        h.accounts.known_branches.add(uuid.UUID(branch_id))

        response = h.client.post(
            "/accounts/me", json={"currency": "EUR", "branch_id": str(uuid.uuid4())}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["currency"] == "USD"
        assert body["customer_id"] == customer_id
        assert body["balance"] == 0


def test_post_accounts_me_409_when_customer_already_has_an_account():
    h = build()
    with h.client:
        branch_id = _create_active_branch(h)
        customer_id = _link_current_customer(h)
        h.accounts.known_customers.add(uuid.UUID(customer_id))
        h.accounts.known_branches.add(uuid.UUID(branch_id))

        first = h.client.post("/accounts/me")
        second = h.client.post("/accounts/me")

        assert first.status_code == 201
        assert second.status_code == 409


def test_post_accounts_me_409_even_when_the_only_existing_account_is_closed():
    h = build()
    with h.client:
        branch_id = _create_active_branch(h)
        customer_id = _link_current_customer(h)
        h.accounts.known_customers.add(uuid.UUID(customer_id))
        h.accounts.known_branches.add(uuid.UUID(branch_id))

        created = h.client.post("/accounts/me").json()
        h.client.delete(f"/accounts/{created['account_number']}")

        response = h.client.post("/accounts/me")

        assert response.status_code == 409


def test_post_accounts_me_503_when_no_active_branch_exists():
    h = build()
    with h.client:
        customer_id = _link_current_customer(h)
        h.accounts.known_customers.add(uuid.UUID(customer_id))

        response = h.client.post("/accounts/me")

        assert response.status_code == 503
