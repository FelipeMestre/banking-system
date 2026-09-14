"""RED for FX-7/FX-4: router margin math, shape, no leak, 502, thin."""

from openbankapi.tests.fakes import FakeCache, FakeForeignExchangeRepository
from openbankapi.tests.conftest import build
from openbankapi.domain.exceptions import RateNotAvailableError


def test_shape_and_calc():
    # mids EUR=0.8613 GBP=0.74 -> buy=mid*0.99 sell=mid*1.01
    repo = FakeForeignExchangeRepository(rates={"EUR": 0.8613, "GBP": 0.74})
    harness = build(cache=FakeCache(), fx_repo=repo)
    with harness.client:
        resp = harness.client.get("/foreign-exchange-rates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "rates" in body
    rates = {r["pair"]: r for r in body["rates"]}
    assert "USD_EUR" in rates and "USD_GBP" in rates
    eur = rates["USD_EUR"]
    gbp = rates["USD_GBP"]
    # check keys exactly: pair, display_buy, display_sell — no mid_rate/margin leak
    assert set(eur.keys()) == {"pair", "display_buy", "display_sell"}
    assert set(gbp.keys()) == {"pair", "display_buy", "display_sell"}
    assert eur["pair"] == "USD_EUR"
    assert gbp["pair"] == "USD_GBP"
    # margin math
    assert eur["display_buy"] == 0.8613 * 0.99
    assert eur["display_sell"] == 0.8613 * 1.01
    assert gbp["display_buy"] == 0.74 * 0.99
    assert gbp["display_sell"] == 0.74 * 1.01
    # ensure no leak of internal field
    text = resp.text
    assert "mid_rate" not in text
    assert "margin" not in text.lower()
    assert "MARGIN" not in text


def test_second_call_within_ttl_zero_external_calls():
    repo = FakeForeignExchangeRepository(rates={"EUR": 0.9, "GBP": 0.8})
    cache = FakeCache()
    harness = build(cache=cache, fx_repo=repo)
    with harness.client:
        first = harness.client.get("/foreign-exchange-rates")
        assert first.status_code == 200
        assert repo.calls == 1
        second = harness.client.get("/foreign-exchange-rates")
        assert second.status_code == 200
        # second hit reads from cache, no repo call
        assert repo.calls == 1, "warm hit must not call repo again"
        assert first.json() == second.json()


def test_502_on_empty_after_usd_filter():
    repo = FakeForeignExchangeRepository(raise_error=RateNotAvailableError("empty"))
    harness = build(cache=FakeCache(), fx_repo=repo)
    with harness.client:
        resp = harness.client.get("/foreign-exchange-rates")
    assert resp.status_code == 502, resp.text
    body = resp.json()
    # error envelope from error_handlers
    assert "error" in body


def test_thin_router_no_redis_httpx_ttl_imports():
    from pathlib import Path

    src = Path("openbankapi/api/v1/routers/foreign_exchange_rate_router.py").read_text().lower()
    assert "import httpx" not in src
    assert "from httpx" not in src
    assert "import redis" not in src
    assert "from redis" not in src
    # router must not know TTL or frankfurter details
    assert "cache_ttl" not in src
    assert "foreign_exchange:mid_rate" not in src
    assert "frankfurter" not in src


def test_margin_constant_is_0_01():
    from pathlib import Path
    import ast

    src = Path("openbankapi/api/v1/routers/foreign_exchange_rate_router.py").read_text()
    # look for MARGIN = 0.01 literal
    assert "MARGIN" in src
    # parse assignment (handle both Assign and AnnAssign)
    tree = ast.parse(src)
    found = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "MARGIN":
                    assert isinstance(node.value, ast.Constant)
                    assert node.value.value == 0.01
                    found = True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "MARGIN":
                assert isinstance(node.value, ast.Constant)
                assert node.value.value == 0.01
                found = True
    assert found, "MARGIN = 0.01 not found as top-level constant"


def test_no_leak_mid_rate_in_response_even_on_partial():
    # Ensure partial miss path also does not leak
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    # pre-populate EUR only
    cache = FakeCache(
        store={
            "foreign_exchange:mid_rate:USD_EUR": {
                "mid_rate": 0.8613,
                "fetched_at": "2026-09-01T00:00:00+00:00",
            }
        }
    )
    repo = FakeForeignExchangeRepository(rates={"EUR": 0.8613, "GBP": 0.74})
    # need service manually to control partial scenario via router?
    # Instead use build with same cache
    harness = build(cache=cache, fx_repo=repo)
    with harness.client:
        resp = harness.client.get("/foreign-exchange-rates")
    assert resp.status_code == 200
    assert "mid_rate" not in resp.text
