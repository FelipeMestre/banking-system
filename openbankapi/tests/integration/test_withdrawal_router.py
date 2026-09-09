"""RED for POST /admin/withdrawals router — mirrors test_deposit_router.py,
plus a declined path deposit never needed."""

import asyncio
import uuid

from fastapi.testclient import TestClient

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.config.dependencies import get_current_user, get_account_repository
from openbankapi.infra.kafka.status_registry import StatusRegistry
from openbankapi.tests.fakes import FakeAccountRepository, FakeCache, FakePublisher


def _make_app_with_fakes(account_repo=None, registry=None, publisher=None, fx_cache_service=None, admin_claims=None):
    settings = Settings(withdrawal_status_topic="withdrawal-status")
    publisher = publisher or FakePublisher()
    cache = FakeCache()
    registry = registry or StatusRegistry()
    account_repo = account_repo or FakeAccountRepository(known_customers={uuid.uuid4()}, known_branches={uuid.uuid4()})
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
        withdrawal_status_registry=registry,
        foreign_exchange_cache_service=fx_cache,  # type: ignore
    )
    from openbankapi.config.dependencies import get_account_repository

    app.dependency_overrides[get_account_repository] = lambda: account_repo

    if admin_claims is not None:
        async def _admin():
            return admin_claims

        app.dependency_overrides[get_current_user] = _admin
    else:
        async def _default_admin():
            return {"sub": "admin-42", "permissions": ["write:admin"], "scope": "write:admin", "aud": "https://openbank.api/com/auth"}

        app.dependency_overrides[get_current_user] = _default_admin

    return app, publisher, registry, account_repo, fx_cache, fx_repo


def _make_active_account(balance=100000, currency="EUR"):
    import datetime as dt

    from openbankapi.domain.model import Account, AccountStatus

    return Account(
        id=uuid.uuid4(),
        account_number="1234567890123456",
        currency=currency,
        customer_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        balance=balance,
        status=AccountStatus.ACTIVE,
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )


def test_unknown_account_returns_404_no_publish():
    account_repo = FakeAccountRepository()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "9999999999999999", "amount": 45540, "currency": "EUR", "reason": "atm withdrawal"},
        )
    assert resp.status_code == 404
    assert publisher.published == []


def test_amount_zero_returns_422():
    account_repo = FakeAccountRepository()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "1234567890123456", "amount": 0, "currency": "EUR"},
        )
    assert resp.status_code == 422
    assert "amount must be positive" in resp.text.lower()


def test_happy_same_currency_returns_200():
    account_repo = FakeAccountRepository()
    acc = _make_active_account(balance=100000, currency="EUR")
    account_repo.rows[acc.account_number] = acc

    registry = StatusRegistry()
    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo, registry=registry)

    async def fake_wait(request_id, timeout=10.0):
        return {"request_id": request_id, "status": "approved", "new_balance": 54460, "amount_applied": 45540}

    registry.wait_for = fake_wait  # type: ignore

    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "1234567890123456", "amount": 45540, "currency": "EUR", "reason": "atm withdrawal"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] is True
    assert body["amount_applied"] == 45540
    assert body.get("applied_rate") is None
    assert body["new_balance"] == 54460
    assert len(publisher.published) == 1
    topic, key, value = publisher.published[0]
    assert topic == "account-events"
    assert key == "1234567890123456"
    assert value["type"] == "withdrawal"


def test_timeout_returns_504_zero_rows():
    account_repo = FakeAccountRepository()
    acc = _make_active_account(balance=100000, currency="EUR")
    account_repo.rows[acc.account_number] = acc
    registry = StatusRegistry()

    async def never_resolves(request_id, timeout=10.0):
        await asyncio.sleep(0.05)
        return None

    registry.wait_for = never_resolves  # type: ignore

    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo, registry=registry)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "1234567890123456", "amount": 45540, "currency": "EUR"},
        )
    assert resp.status_code == 504
    assert resp.json()["detail"] == "withdrawal confirmation timeout"
    assert len(publisher.published) == 1


def test_openapi_has_withdrawal():
    account_repo = FakeAccountRepository()
    app, _, _, _, _, _ = _make_app_with_fakes(account_repo=account_repo)
    with TestClient(app) as client:
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/admin/withdrawals" in paths
    assert "post" in paths["/admin/withdrawals"]


def test_cross_currency_converts():
    account_repo = FakeAccountRepository()
    acc = _make_active_account(balance=100000, currency="EUR")
    account_repo.rows[acc.account_number] = acc
    registry = StatusRegistry()

    # debit's adjustment is `1 + MARGIN` (not `1 - MARGIN` like credit/deposit):
    # 50000 * 0.92 * 1.01 = 46460.
    async def fake_wait(request_id, timeout=10.0):
        return {
            "request_id": request_id,
            "status": "approved",
            "new_balance": 53540,
            "amount_applied": 46460,
            "applied_rate": {
                "pair": "USD_EUR",
                "mid_rate": 0.92,
                "applied_rate": 0.9292,
                "margin": 0.01,
                "direction": "debit",
                "source_ts": "2026-09-09T12:00:00+00:00",
            },
        }

    registry.wait_for = fake_wait  # type: ignore

    app, publisher, registry, _, _, fx_repo = _make_app_with_fakes(account_repo=account_repo, registry=registry)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "1234567890123456", "amount": 50000, "currency": "USD", "reason": "cash"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_applied"] == 46460
    assert body["applied_rate"] is not None
    assert body["applied_rate"]["pair"] == "USD_EUR"
    assert body["new_balance"] == 53540
    _, _, value = publisher.published[0]
    assert value["amount"] == 50000
    assert value["currency"] == "USD"
    assert value["amount_applied"] == 46460


def test_declined_insufficient_funds_returns_200_approved_false():
    account_repo = FakeAccountRepository()
    acc = _make_active_account(balance=1000, currency="EUR")
    account_repo.rows[acc.account_number] = acc
    registry = StatusRegistry()

    async def fake_wait(request_id, timeout=10.0):
        return {"request_id": request_id, "status": "declined", "reason": "insufficient_funds"}

    registry.wait_for = fake_wait  # type: ignore

    app, publisher, registry, _, _, _ = _make_app_with_fakes(account_repo=account_repo, registry=registry)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/withdrawals",
            json={"account_number": "1234567890123456", "amount": 500000, "currency": "EUR"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] is False
    assert body["reason"] == "insufficient_funds"
    assert "amount_applied" not in body
    assert "new_balance" not in body
