"""RED for FX-13/FX-15: POST /foreign-exchange-rates/quote.

Uses `httpx.AsyncClient` + `ASGITransport` against `create_app()`, per this
repo's AGENTS.MD async-client testing convention — distinct from the sibling
`GET /foreign-exchange-rates` tests, which predate that convention and still
use the synchronous `TestClient` via `conftest.py`'s `build()` harness. No
`pytest-asyncio` is installed here, so each async body is driven with
`asyncio.run(...)`, matching `test_foreign_exchange_cache_service.py`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.domain.exceptions import RateNotAvailableError
from openbankapi.domain.service.conversion_service import get_mid_rate
from openbankapi.infra.kafka.status_registry import StatusRegistry
from openbankapi.tests.db_fixtures import rollback_session

RATES = {"EUR": 0.86, "GBP": 0.74}


class _FakeForeignExchangeCacheService:
    """Stands in for `app.state.foreign_exchange_cache_service` (spec FX-13:
    the router reads it straight off `request.app.state`, not via Depends)."""

    def __init__(self, rates=None, raise_error=None):
        self.rates = rates if rates is not None else dict(RATES)
        self.raise_error = raise_error
        self.calls = 0

    async def get_rates(self):
        self.calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        return dict(self.rates)


class _FakePublisher:
    def publish(self, topic, key, value):
        return None


class _FakeCache:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl_seconds=300):
        return None

    async def delete(self, key):
        return None

    async def close(self):
        return None


def _build_app(*, rates=None, raise_error=None):
    fx_cache_service = _FakeForeignExchangeCacheService(rates=rates, raise_error=raise_error)
    app = create_app(
        settings=Settings(),
        cache=_FakeCache(),
        publisher=_FakePublisher(),
        sessionmaker=None,
        status_registry=StatusRegistry(),
        foreign_exchange_cache_service=fx_cache_service,
    )
    return app, fx_cache_service


async def _post_quote(app, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/foreign-exchange-rates/quote", json=payload)


def test_eur_to_usd_debit_matches_conversion_service():
    app, _ = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 10000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        )
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_amount"] == 11744
    assert body["applied_rate"] == pytest.approx(get_mid_rate("EUR", "USD", RATES) * 1.01)


def test_eur_to_usd_credit_matches_conversion_service_and_differs_from_debit():
    app, _ = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 10000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "credit"},
        )
    )
    body = resp.json()
    assert body["final_amount"] == 11512
    assert body["final_amount"] != 11744
    assert body["applied_rate"] == pytest.approx(get_mid_rate("EUR", "USD", RATES) * 0.99)


def test_usd_to_eur_debit_matches_conversion_service():
    app, _ = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 10000, "from_currency": "USD", "to_currency": "EUR", "customer_effect": "debit"},
        )
    )
    body = resp.json()
    assert body["final_amount"] == 8686
    assert body["applied_rate"] == pytest.approx(get_mid_rate("USD", "EUR", RATES) * 1.01)


def test_usd_to_eur_credit_matches_conversion_service_and_differs_from_debit():
    app, _ = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 10000, "from_currency": "USD", "to_currency": "EUR", "customer_effect": "credit"},
        )
    )
    body = resp.json()
    assert body["final_amount"] == 8514
    assert body["final_amount"] != 8686
    assert body["applied_rate"] == pytest.approx(get_mid_rate("USD", "EUR", RATES) * 0.99)


def test_same_currency_passthrough_via_http():
    app, fx = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 5000, "from_currency": "EUR", "to_currency": "EUR", "customer_effect": "debit"},
        )
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_amount"] == 5000
    assert body["applied_rate"] is None
    assert fx.calls == 1


def test_non_positive_amount_rejected_before_any_cache_call():
    app, fx = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 0, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        )
    )
    assert resp.status_code == 422
    assert fx.calls == 0


def test_negative_amount_rejected():
    app, fx = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": -100, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        )
    )
    assert resp.status_code == 422
    assert fx.calls == 0


def test_rate_unavailable_maps_to_503_not_the_global_502():
    app, _ = _build_app(raise_error=RateNotAvailableError("no rates"))
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 1000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        )
    )
    assert resp.status_code == 503, resp.text


def test_response_never_leaks_internal_pricing_fields():
    app, _ = _build_app()
    resp = asyncio.run(
        _post_quote(
            app,
            {"amount": 10000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        )
    )
    body = resp.json()
    assert set(body.keys()) == {"final_amount", "from_currency", "to_currency", "applied_rate"}
    assert "mid_rate" not in resp.text
    assert "margin" not in resp.text.lower()


def test_quote_never_writes_to_applied_rates(fx_test_dsn):
    async def _run():
        async with rollback_session(fx_test_dsn) as session:
            before = (await session.execute(text("SELECT count(*) FROM applied_rates"))).scalar_one()
            assert before == 0

        payloads = [
            {"amount": 10000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
            {"amount": 10000, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "credit"},
            {"amount": 5000, "from_currency": "EUR", "to_currency": "EUR", "customer_effect": "debit"},
            {"amount": 0, "from_currency": "EUR", "to_currency": "USD", "customer_effect": "debit"},
        ]
        app, _ = _build_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for payload in payloads:
                await client.post("/foreign-exchange-rates/quote", json=payload)

        error_app, _ = _build_app(raise_error=RateNotAvailableError("no rates"))
        error_transport = ASGITransport(app=error_app)
        async with AsyncClient(transport=error_transport, base_url="http://test") as client:
            await client.post("/foreign-exchange-rates/quote", json=payloads[0])

        async with rollback_session(fx_test_dsn) as session:
            after = (await session.execute(text("SELECT count(*) FROM applied_rates"))).scalar_one()
            assert after == 0

    asyncio.run(_run())


def test_insert_is_never_called_from_the_router_source():
    src = Path("openbankapi/api/v1/routers/foreign_exchange_rate_router.py").read_text()
    assert "insert(" not in src
