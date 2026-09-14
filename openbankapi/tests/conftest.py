"""Builds the real app with fake ports — no broker, no Postgres, no Redis."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.config.dependencies import (
    get_account_repository,
    get_admin_action_repository,
    get_applied_rate_repository,
    get_current_user,
    get_card_account_repository,
    get_card_movement_repository,
    get_card_repository,
    get_customer_repository,
    get_installment_repository,
    get_statement_repository,
    get_transaction_repository,
)
from openbankapi.infra.kafka.status_registry import StatusRegistry

_DEFAULT_ADMIN_CLAIMS = {
    "sub": "test-admin",
    "permissions": ["read:admin", "write:admin"],
    "scope": "read:admin write:admin",
    "aud": "https://openbank.api/com/auth",
}

from .fakes import (
    FakeCustomerRepository,
    FakeAccountRepository,
    FakeAppliedRateRepository,
    FakeCardAccountAdminActionRepository,
    FakeCardAccountRepository,
    FakeCardMovementRepository,
    FakeCardRepository,
    FakeInstallmentRepository,
    FakePublisher,
    FakeCache,
    FakeStatementRepository,
    FakeTransactionRepository,
    FakeForeignExchangeRepository,
)
from .db_fixtures import TEST_DATABASE_DSN, migrate_to_head


class Harness:
    def __init__(
        self, client, publisher, cache, registry, repos, settings,
        fx_cache_service=None, fx_repo=None, card_accounts=None, cards=None,
        card_movements=None, installments=None, applied_rates=None, statements=None,
        admin_actions=None,
    ):
        self.client = client
        self.publisher = publisher
        self.cache = cache
        self.registry = registry
        self.customers, self.accounts, self.transactions = repos
        self.settings = settings
        self.fx_cache_service = fx_cache_service
        self.fx_repo = fx_repo
        self.card_accounts = card_accounts
        self.cards = cards
        self.card_movements = card_movements
        self.installments = installments
        self.applied_rates = applied_rates
        self.statements = statements
        self.admin_actions = admin_actions


def build(
    *,
    cache=None,
    accounts=None,
    transactions=None,
    fx_repo=None,
    fx_cache_service=None,
    with_admin: bool = True,
    admin_claims: dict | None = None,
    card_accounts=None,
    cards=None,
    card_movements=None,
    installments=None,
    applied_rates=None,
    statements=None,
    admin_actions=None,
) -> Harness:
    # lazy imports to avoid circular deps during app wiring
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    publisher = FakePublisher()
    cache = cache or FakeCache()
    registry = StatusRegistry()

    customers = FakeCustomerRepository()
    accounts = accounts or FakeAccountRepository()
    transactions = transactions or FakeTransactionRepository()

    fx_repo = fx_repo or FakeForeignExchangeRepository()
    fx_cache_service = fx_cache_service or ForeignExchangeCacheService(cache, fx_repo)

    card_accounts = card_accounts or FakeCardAccountRepository()
    cards = cards or FakeCardRepository()
    card_movements = card_movements or FakeCardMovementRepository(cards=cards)
    installments = installments or FakeInstallmentRepository()
    applied_rates = applied_rates or FakeAppliedRateRepository()
    statements = statements or FakeStatementRepository()
    admin_actions = admin_actions or FakeCardAccountAdminActionRepository()

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
    app.dependency_overrides[get_customer_repository] = lambda: customers
    app.dependency_overrides[get_account_repository] = lambda: accounts
    app.dependency_overrides[get_transaction_repository] = lambda: transactions
    if with_admin:
        claims = admin_claims if admin_claims is not None else _DEFAULT_ADMIN_CLAIMS
        # Use async lambda for get_current_user (it is async def)
        async def _default_admin():
            return claims

        app.dependency_overrides[get_current_user] = _default_admin
        
    app.dependency_overrides[get_card_account_repository] = lambda: card_accounts
    app.dependency_overrides[get_card_repository] = lambda: cards
    app.dependency_overrides[get_card_movement_repository] = lambda: card_movements
    app.dependency_overrides[get_installment_repository] = lambda: installments
    app.dependency_overrides[get_applied_rate_repository] = lambda: applied_rates
    app.dependency_overrides[get_statement_repository] = lambda: statements
    app.dependency_overrides[get_admin_action_repository] = lambda: admin_actions
    client = TestClient(app)
    # also attach for router tests that use app.state directly
    app.state.fx_repo = fx_repo  # type: ignore[attr-defined]
    return Harness(client, publisher, cache, registry,
                   (customers, accounts, transactions), settings, fx_cache_service, fx_repo,
                   card_accounts, cards, card_movements, installments, applied_rates, statements, admin_actions)


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
    customer_id = uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={customer_id})
    h = build(accounts=accounts)
    h.customer_id = customer_id
    with h.client:
        yield h
