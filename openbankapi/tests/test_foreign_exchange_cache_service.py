"""RED for FX-5/FX-6: ForeignExchangeCacheService cache-aside, TTL, fetch-once."""

import asyncio
import json


class FakeCache:
    def __init__(self, store=None):
        self.store: dict = store or {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, dict, int]] = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return self.store.get(key)

    async def set(self, key: str, value, ttl_seconds: int = 300):
        self.set_calls.append((key, value, ttl_seconds))
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)

    async def close(self):
        return None


class FakeRepo:
    def __init__(self, rates=None, raise_error=None):
        self.rates = rates or {"EUR": 0.8613, "GBP": 0.74}
        self.raise_error = raise_error
        self.calls = 0

    async def get_all_mid_rates(self):
        self.calls += 1
        if self.raise_error:
            raise self.raise_error
        return dict(self.rates)


def test_hit_no_http():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    # EUR and GBP already cached as dicts (ICacheService decoded)
    store = {
        "foreign_exchange:mid_rate:USD_EUR": {"mid_rate": 0.8613, "fetched_at": "2026-09-01T00:00:00+00:00"},
        "foreign_exchange:mid_rate:USD_GBP": {"mid_rate": 0.74, "fetched_at": "2026-09-01T00:00:00+00:00"},
    }
    cache = FakeCache(store=store)
    repo = FakeRepo()
    svc = ForeignExchangeCacheService(cache, repo)

    rates = asyncio.run(svc.get_rates())
    assert rates == {"EUR": 0.8613, "GBP": 0.74}
    assert repo.calls == 0
    assert len(cache.set_calls) == 0


def test_ttl_on_save():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
        CACHE_TTL_SECONDS,
    )

    assert CACHE_TTL_SECONDS == 86400

    cache = FakeCache(store={})
    repo = FakeRepo(rates={"EUR": 0.9, "GBP": 0.8})
    svc = ForeignExchangeCacheService(cache, repo)

    rates = asyncio.run(svc.get_rates())
    assert rates == {"EUR": 0.9, "GBP": 0.8}
    # should have saved both keys with TTL 86400
    assert len(cache.set_calls) == 2
    for key, value, ttl in cache.set_calls:
        assert ttl == 86400
        assert "mid_rate" in value
        assert "fetched_at" in value
        assert key in ("foreign_exchange:mid_rate:USD_EUR", "foreign_exchange:mid_rate:USD_GBP")


def test_both_missing_single_fetch():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    cache = FakeCache(store={})
    repo = FakeRepo(rates={"EUR": 0.8613, "GBP": 0.74})
    svc = ForeignExchangeCacheService(cache, repo)

    rates = asyncio.run(svc.get_rates())
    assert rates == {"EUR": 0.8613, "GBP": 0.74}
    assert repo.calls == 1, "must fetch exactly once even if both missing"
    assert len(cache.set_calls) == 2


def test_one_hit_one_miss_still_fetch_once_and_merge():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    store = {
        "foreign_exchange:mid_rate:USD_EUR": {"mid_rate": 0.8613, "fetched_at": "2026-09-01T00:00:00+00:00"},
    }
    cache = FakeCache(store=store)
    # repo returns both EUR and GBP fresh, but EUR should be reused from cache in result
    repo = FakeRepo(rates={"EUR": 0.9999, "GBP": 0.74})
    svc = ForeignExchangeCacheService(cache, repo)

    rates = asyncio.run(svc.get_rates())
    # EUR must be cached value (reused), GBP from fresh
    # If implementation does rates.update(fresh), EUR would be 0.9999 — we assert reuse
    assert rates["EUR"] == 0.8613, "EUR should be reused from cache, not overwritten by fresh"
    assert rates["GBP"] == 0.74
    assert repo.calls == 1


def test_second_call_no_hit_when_warm():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    cache = FakeCache(store={})
    repo = FakeRepo(rates={"EUR": 0.8613, "GBP": 0.74})
    svc = ForeignExchangeCacheService(cache, repo)

    first = asyncio.run(svc.get_rates())
    assert repo.calls == 1
    # second call should be warm (cache now populated)
    second = asyncio.run(svc.get_rates())
    assert second == first
    assert repo.calls == 1, "second warm hit must make zero repo calls"


def test_payload_shape_json_serializable():
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    cache = FakeCache(store={})
    repo = FakeRepo(rates={"EUR": 0.5, "GBP": 0.6})
    svc = ForeignExchangeCacheService(cache, repo)
    asyncio.run(svc.get_rates())
    for key, value, ttl in cache.set_calls:
        # value must be dict with mid_rate and fetched_at ISO8601 string
        assert isinstance(value, dict)
        # should be json serializable without double-encode
        serialized = json.dumps(value)
        parsed = json.loads(serialized)
        assert parsed["mid_rate"] == value["mid_rate"]
        assert isinstance(parsed["fetched_at"], str)


def test_handling_string_cached_value():
    """Real ICacheService decodes JSON, but be robust if raw string is returned."""
    from openbankapi.infra.cache.services.foreign_exchange_cache_service import (
        ForeignExchangeCacheService,
    )

    # Simulate raw redis string (json string) — service should handle both
    raw_eur = json.dumps({"mid_rate": 0.8613, "fetched_at": "2026-09-01T00:00:00+00:00"})
    raw_gbp = json.dumps({"mid_rate": 0.74, "fetched_at": "2026-09-01T00:00:00+00:00"})
    store = {
        "foreign_exchange:mid_rate:USD_EUR": raw_eur,
        "foreign_exchange:mid_rate:USD_GBP": raw_gbp,
    }
    cache = FakeCache(store=store)
    repo = FakeRepo()
    svc = ForeignExchangeCacheService(cache, repo)
    rates = asyncio.run(svc.get_rates())
    assert rates == {"EUR": 0.8613, "GBP": 0.74}
    assert repo.calls == 0


def test_no_httpx_import_in_cache():
    from pathlib import Path

    src = Path("openbankapi/infra/cache/services/foreign_exchange_cache_service.py").read_text().lower()
    assert "import httpx" not in src
    assert "from httpx" not in src
    assert "import redis" not in src
    assert "from redis" not in src
    # should not import concrete frankfurter repo
    assert "frankfurter" not in src


def test_only_owner_of_fx_keys():
    """Only cache service should own foreign_exchange:mid_rate keys — router/repo must not."""
    from pathlib import Path

    for p in Path("openbankapi").rglob("*.py"):
        if p.match("*/infra/cache/services/foreign_exchange_cache_service.py"):
            continue
        if "tests/" in str(p):
            continue
        src = p.read_text()
        if "foreign_exchange:mid_rate" in src:
            assert False, f"key ownership violation in {p}: only cache service should use this key"
