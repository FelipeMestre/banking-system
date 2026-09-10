"""RED for Task 3.3 — POST /admin/deposits router."""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.config.dependencies import get_current_user, get_account_repository
from openbankapi.infra.kafka.status_registry import StatusRegistry
from openbankapi.tests.fakes import FakeAccountRepository, FakeCache, FakePublisher


def _make_app_with_fakes(account_repo=None, registry=None, publisher=None, fx_cache_service=None, admin_claims=None):
    settings = Settings(deposit_status_topic="deposit-status")
    publisher = publisher or FakePublisher()
    cache = FakeCache()
    registry = registry or StatusRegistry()
    account_repo = account_repo or FakeAccountRepository(known_customers={uuid.uuid4()})
    # need a customer for account creation? but we will directly insert account via Fake
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import ForeignExchangeCacheService
    from openbankapi.tests.fakes import FakeForeignExchangeRepository

    fx_repo = FakeForeignExchangeRepository(rates={"EUR": 0.92, "GBP": 0.74, "USD": 1.0})
    fx_cache = fx_cache_service or ForeignExchangeCacheService(cache, fx_repo)

    app = create_app(
        settings=settings,
        cache=cache,
        publisher=publisher,
        sessionmaker=None,  # type: ignore
        status_registry=StatusRegistry(),
        deposit_status_registry=registry,
        foreign_exchange_cache_service=fx_cache,  # type: ignore
    )
    # override account repo
    from openbankapi.config.dependencies import get_account_repository

    app.dependency_overrides[get_account_repository] = lambda: account_repo
    # also need to override deposit registry dep? create_app already stashes it

    if admin_claims is not None:
        async def _admin():
            return admin_claims

        app.dependency_overrides[get_current_user] = _admin
    else:
        async def _default_admin():
            return {"sub": "admin-42", "permissions": ["write:admin"], "scope": "write:admin", "aud": "https://openbank.api/com/auth"}

        app.dependency_overrides[get_current_user] = _default_admin

    return app, publisher, registry, account_repo, fx_cache, fx_repo


def test_unknown_account_returns_404_no_publish():
    from openbankapi.domain.model import Account, AccountStatus
    import datetime as dt

    account_repo = FakeAccountRepository()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/deposits",
            json={"account_number": "9999999999999999", "amount": 50000, "currency": "EUR", "reason": "cash branch 42"},
        )
    assert resp.status_code == 404
    assert publisher.published == []


def test_amount_zero_returns_422():
    account_repo = FakeAccountRepository()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/deposits",
            json={"account_number": "1234567890123456", "amount": 0, "currency": "EUR"},
        )
    assert resp.status_code == 422
    assert "amount must be positive" in resp.text.lower()


def test_happy_same_currency_returns_200():
    import datetime as dt

    from openbankapi.domain.model import Account, AccountStatus

    account_repo = FakeAccountRepository()
    # insert EUR account
    acc = Account(
        id=uuid.uuid4(),
        account_number="1234567890123456",
        currency="EUR",
        customer_id=uuid.uuid4(),
        balance=100000,
        status=AccountStatus.ACTIVE,
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    account_repo.rows[acc.account_number] = acc

    registry = StatusRegistry()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo, registry=registry)

    # Need to simulate Flink resolving: run waiter in background? For this test, we will manually resolve after a short delay
    # The registry wait_for will block until we resolve; we can spawn a thread to resolve after 0.05s
    import threading

    def resolve_later():
        import time

        time.sleep(0.05)
        # simulate deposit-status event: must have request_id matching what router publishes
        # We don't know request_id beforehand, so we will poll publisher then resolve
        # Instead, we override registry.wait_for to return a canned event immediately for this test
        pass

    # Monkey patch registry.wait_for to return success without needing real Kafka
    original_wait = registry.wait_for

    async def fake_wait(request_id, timeout=10.0):
        return {"request_id": request_id, "status": "approved", "new_balance": 150000, "amount_applied": 50000}

    registry.wait_for = fake_wait  # type: ignore

    with TestClient(app) as client:
        resp = client.post(
            "/admin/deposits",
            json={"account_number": "1234567890123456", "amount": 50000, "currency": "EUR", "reason": "cash branch 42"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] is True
    assert body["amount_applied"] == 50000
    assert body.get("applied_rate") is None
    assert body["new_balance"] == 150000
    # publisher should have one deposit event keyed by account_number
    assert len(publisher.published) == 1
    topic, key, value = publisher.published[0]
    assert topic == "account-events"
    assert key == "1234567890123456"
    assert value["type"] == "deposit"


def test_timeout_returns_504_zero_rows():
    import datetime as dt

    from openbankapi.domain.model import Account, AccountStatus

    account_repo = FakeAccountRepository()
    acc = Account(
        id=uuid.uuid4(),
        account_number="1234567890123456",
        currency="EUR",
        customer_id=uuid.uuid4(),
        balance=100000,
        status=AccountStatus.ACTIVE,
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    account_repo.rows[acc.account_number] = acc
    registry = StatusRegistry()

    async def never_resolves(request_id, timeout=10.0):
        # simulate timeout by returning None after short wait
        await asyncio.sleep(0.05)
        return None

    registry.wait_for = never_resolves  # type: ignore

    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo, registry=registry)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/deposits",
            json={"account_number": "1234567890123456", "amount": 50000, "currency": "EUR"},
        )
    assert resp.status_code == 504
    # even on timeout, the deposit event was still published (router publishes before waiting)
    # but no transactions/deposits rows exist — that is downstream, not here; we just check no extra side effect
    assert len(publisher.published) == 1


def test_openapi_has_deposit():
    account_repo = FakeAccountRepository()
    app, _, _, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/admin/deposits" in paths
    assert "post" in paths["/admin/deposits"]


def test_cross_currency_converts():
    import datetime as dt

    from openbankapi.domain.model import Account, AccountStatus

    account_repo = FakeAccountRepository()
    acc = Account(
        id=uuid.uuid4(),
        account_number="1234567890123456",
        currency="EUR",
        customer_id=uuid.uuid4(),
        balance=100000,
        status=AccountStatus.ACTIVE,
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    account_repo.rows[acc.account_number] = acc
    registry = StatusRegistry()

    async def fake_wait(request_id, timeout=10.0):
        # amount_applied 45540 for USD->EUR
        return {"request_id": request_id, "status": "approved", "new_balance": 145540, "amount_applied": 45540, "applied_rate": {"pair": "USD_EUR", "mid_rate": 0.92, "applied_rate": 0.9108, "margin": 0.01, "direction": "credit", "source_ts": "2026-09-03T12:00:00+00:00"}}

    registry.wait_for = fake_wait  # type: ignore

    app, publisher, registry, _, _, fx_repo = _make_app_with_fakes(account_repo=account_repo, registry=registry)
    # need to set fx_repo rates to EUR 0.92 for USD->EUR
    # FakeForeignExchangeRepository already has EUR 0.92
    with TestClient(app) as client:
        resp = client.post(
            "/admin/deposits",
            json={"account_number": "1234567890123456", "amount": 50000, "currency": "USD", "reason": "cash"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_applied"] == 45540
    assert body["applied_rate"] is not None
    assert body["applied_rate"]["pair"] == "USD_EUR"
    assert body["new_balance"] == 145540
    # check published event has applied_rate
    _, _, value = publisher.published[0]
    assert value["amount"] == 50000
    assert value["currency"] == "USD"
    assert value["amount_applied"] == 45540
