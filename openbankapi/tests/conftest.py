"""Builds the real app with fake ports — no broker, no Postgres, no Redis."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.config.dependencies import (
    get_account_repository,
    get_branch_repository,
    get_card_account_repository,
    get_card_repository,
    get_customer_repository,
    get_location_repository,
    get_transaction_repository,
)
from openbankapi.infra.kafka.status_registry import StatusRegistry

from .fakes import (
    FakeCustomerRepository,
    FakeAccountRepository,
    FakeCardAccountRepository,
    FakeCardRepository,
    FakeLocationRepository,
    FakePublisher,
    FakeBranchRepository,
    FakeCache,
    FakeTransactionRepository,
    FakeForeignExchangeRepository,
)
from .db_fixtures import TEST_DATABASE_DSN, migrate_to_head


class Harness:
    def __init__(
        self, client, publisher, cache, registry, repos, settings,
        fx_cache_service=None, fx_repo=None, card_accounts=None, cards=None,
    ):
        self.client = client
        self.publisher = publisher
        self.cache = cache
        self.registry = registry
        self.locations, self.branches, self.customers, self.accounts, self.transactions = repos
        self.settings = settings
        self.fx_cache_service = fx_cache_service
        self.fx_repo = fx_repo
        self.card_accounts = card_accounts
        self.cards = cards


def build(
    *,
    cache=None,
    accounts=None,
    branches=None,
    transactions=None,
    fx_repo=None,
    fx_cache_service=None,
    card_accounts=None,
    cards=None,
) -> Harness:
    # lazy imports to avoid circular deps during app wiring
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    publisher = FakePublisher()
    cache = cache or FakeCache()
    registry = StatusRegistry()

    locations = FakeLocationRepository()
    branches = branches or FakeBranchRepository()
    customers = FakeCustomerRepository()
    accounts = accounts or FakeAccountRepository()
    transactions = transactions or FakeTransactionRepository()

    fx_repo = fx_repo or FakeForeignExchangeRepository()
    fx_cache_service = fx_cache_service or ForeignExchangeCacheService(cache, fx_repo)

    card_accounts = card_accounts or FakeCardAccountRepository()
    cards = cards or FakeCardRepository()

    try:
        app = create_app(
            settings=settings,
            cache=cache,
            publisher=publisher,
            sessionmaker=None,  # unused: every repository dependency is overridden below
            status_registry=registry,
            foreign_exchange_cache_service=fx_cache_service,  # type: ignore[call-arg]
        )
    except TypeError:
        # Work unit 2 runs before app.py gains the param — fall back to direct state injection
        app = create_app(
            settings=settings,
            cache=cache,
            publisher=publisher,
            sessionmaker=None,
            status_registry=registry,
        )
        app.state.foreign_exchange_cache_service = fx_cache_service  # type: ignore[attr-defined]
    app.dependency_overrides[get_location_repository] = lambda: locations
    app.dependency_overrides[get_branch_repository] = lambda: branches
    app.dependency_overrides[get_customer_repository] = lambda: customers
    app.dependency_overrides[get_account_repository] = lambda: accounts
    app.dependency_overrides[get_transaction_repository] = lambda: transactions
    app.dependency_overrides[get_card_account_repository] = lambda: card_accounts
    app.dependency_overrides[get_card_repository] = lambda: cards
    client = TestClient(app)
    # also attach for router tests that use app.state directly
    app.state.fx_repo = fx_repo  # type: ignore[attr-defined]
    return Harness(client, publisher, cache, registry,
                   (locations, branches, customers, accounts, transactions), settings, fx_cache_service, fx_repo,
                   card_accounts, cards)


@pytest.fixture
def harness():
    h = build()
    with h.client:
        yield h


@pytest.fixture(scope="session")
def fx_test_dsn() -> str:
    """Dedicated real-Postgres test database, migrated to `head` once per
    session — see `db_fixtures.py` for why this is a separate database from
    the shared dev one (FX-14, "Known Gap" in the tasks artifact)."""
    migrate_to_head(TEST_DATABASE_DSN)
    return TEST_DATABASE_DSN


@pytest.fixture
def wired():
    """A harness whose reference data already exists, ready for account work."""
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
    h = build(accounts=accounts)
    h.customer_id, h.branch_id = customer_id, branch_id
    with h.client:
        yield h
