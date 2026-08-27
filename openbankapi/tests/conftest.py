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
    get_customer_repository,
    get_location_repository,
)
from openbankapi.infra.kafka.status_registry import StatusRegistry

from .fakes import (
    FakeCustomerRepository,
    FakeAccountRepository,
    FakeLocationRepository,
    FakePublisher,
    FakeBranchRepository,
    FakeCache,
)


class Harness:
    def __init__(self, client, publisher, cache, registry, repos, settings):
        self.client = client
        self.publisher = publisher
        self.cache = cache
        self.registry = registry
        self.locations, self.branches, self.customers, self.accounts = repos
        self.settings = settings


def build(*, cache=None, accounts=None, branches=None) -> Harness:
    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    publisher = FakePublisher()
    cache = cache or FakeCache()
    registry = StatusRegistry()

    locations = FakeLocationRepository()
    branches = branches or FakeBranchRepository()
    customers = FakeCustomerRepository()
    accounts = accounts or FakeAccountRepository()

    app = create_app(
        settings=settings,
        cache=cache,
        publisher=publisher,
        sessionmaker=None,  # unused: every repository dependency is overridden below
        status_registry=registry,
    )
    app.dependency_overrides[get_location_repository] = lambda: locations
    app.dependency_overrides[get_branch_repository] = lambda: branches
    app.dependency_overrides[get_customer_repository] = lambda: customers
    app.dependency_overrides[get_account_repository] = lambda: accounts
    client = TestClient(app)
    return Harness(client, publisher, cache, registry,
                   (locations, branches, customers, accounts), settings)


@pytest.fixture
def harness():
    h = build()
    with h.client:
        yield h


@pytest.fixture
def wired():
    """A harness whose reference data already exists, ready for account work."""
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    accounts = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
    h = build(accounts=accounts)
    h.customer_id, h.branch_id = customer_id, branch_id
    with h.client:
        yield h
