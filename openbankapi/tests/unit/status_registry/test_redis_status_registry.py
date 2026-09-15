"""`_RedisStatusRegistry` unit tests (Tasks 1.1, 1.4, 1.6) — driven against
`FakeRedisStatusRegistryClient`, no real Redis. The `wait_for`
subscribe-before-check race against REAL Redis timing lives in
`tests/integration/test_redis_status_registry.py` (opt-in, CI-tagged); this
module unit-tests the registry's own logic, not Redis's network behavior.

No `pytest-asyncio` in this repo (see `tests/db_fixtures.py`) — every async
body is driven with `asyncio.run(scenario())`, matching the rest of the suite.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

from openbankapi.infra.status_registry.repositories.redis_status_registry import (
    get_redis_status_registry,
)

from .fake_redis_client import FakeRedisStatusRegistryClient


def _registry(client=None, *, domain="transfer", ttl_seconds=240):
    client = client or FakeRedisStatusRegistryClient()
    return get_redis_status_registry(client, domain, ttl_seconds), client


def test_resolve_sets_the_ttl_key_and_publishes():
    async def scenario():
        registry, client = _registry()
        await registry.resolve({"request_id": "r1", "status": "approved"})
        assert json.loads(client._store["status:transfer:r1"]) == {
            "request_id": "r1",
            "status": "approved",
        }
        assert client.set_calls == [
            ("status:transfer:r1", json.dumps({"request_id": "r1", "status": "approved"}), 240, True)
        ]

    asyncio.run(scenario())


def test_get_returns_none_on_miss_and_the_event_on_hit():
    async def scenario():
        registry, _ = _registry()
        assert await registry.get("missing") is None
        await registry.resolve({"request_id": "r1", "status": "approved"})
        assert await registry.get("r1") == {"request_id": "r1", "status": "approved"}

    asyncio.run(scenario())


def test_resolve_ignores_an_event_without_request_id():
    async def scenario():
        registry, client = _registry()
        await registry.resolve({"status": "approved"})
        assert client.set_calls == []

    asyncio.run(scenario())


def test_wait_for_returns_cached_value_immediately():
    async def scenario():
        registry, _ = _registry()
        await registry.resolve({"request_id": "r1", "status": "approved"})
        result = await registry.wait_for("r1", timeout=1.0)
        assert result == {"request_id": "r1", "status": "approved"}

    asyncio.run(scenario())


def test_wait_for_times_out_when_never_resolved():
    async def scenario():
        registry, _ = _registry()
        result = await registry.wait_for("never", timeout=0.3)
        assert result is None

    asyncio.run(scenario())


def test_wait_for_subscribes_before_reading_the_cache():
    """The ordering fix itself: a value published the instant a caller
    observes the first cache read (the moment `wait_for` would otherwise
    have already missed it) must still be observed, because `subscribe`
    happened first and the publish lands in its queue regardless."""

    async def scenario():
        client = FakeRedisStatusRegistryClient()
        registry, _ = _registry(client)
        original_get = client.get
        published = False

        async def get_that_publishes_first(key):
            nonlocal published
            if not published:
                published = True
                await registry.resolve({"request_id": "race", "status": "approved"})
            return await original_get(key)

        client.get = get_that_publishes_first  # type: ignore[method-assign]
        result = await registry.wait_for("race", timeout=1.0)
        assert result == {"request_id": "race", "status": "approved"}

    asyncio.run(scenario())


def test_wait_for_wakes_on_a_message_published_after_the_initial_miss():
    async def scenario():
        registry, _ = _registry()

        async def resolve_soon():
            await asyncio.sleep(0.05)
            await registry.resolve({"request_id": "r2", "status": "approved"})

        task = asyncio.ensure_future(resolve_soon())
        result = await registry.wait_for("r2", timeout=2.0)
        await task
        assert result is not None
        assert result["request_id"] == "r2"

    asyncio.run(scenario())


def test_resolve_threadsafe_schedules_without_running_inline():
    async def scenario():
        registry, client = _registry()
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)

        registry.resolve_threadsafe({"request_id": "r3", "status": "approved"})
        # Scheduled, not run synchronously inline.
        assert "status:transfer:r3" not in client._store

        await asyncio.sleep(0.05)
        assert await registry.get("r3") == {"request_id": "r3", "status": "approved"}

    asyncio.run(scenario())


def test_resolve_threadsafe_from_a_real_worker_thread_does_not_block():
    """Exercises the actual cross-thread path `call_soon_threadsafe` exists
    for, proving the calling thread never waits on the Redis round-trip
    `resolve` performs — design's explicit rejection of a blocking
    `run_coroutine_threadsafe(...).result()`."""

    async def scenario():
        registry, _client = _registry()
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)

        started = threading.Event()
        finished = threading.Event()

        def worker():
            started.set()
            t0 = time.monotonic()
            registry.resolve_threadsafe({"request_id": "r4", "status": "approved"})
            elapsed = time.monotonic() - t0
            assert elapsed < 0.05, "resolve_threadsafe must not block the caller thread"
            finished.set()

        thread = threading.Thread(target=worker)
        thread.start()
        started.wait(timeout=1.0)
        thread.join(timeout=1.0)
        assert finished.is_set()

        await asyncio.sleep(0.05)
        assert await registry.get("r4") is not None

    asyncio.run(scenario())


def test_resolve_threadsafe_logs_an_unhandled_exception(caplog):
    class RaisingClient(FakeRedisStatusRegistryClient):
        async def set(self, key, value, *, ex, nx=False):
            raise RuntimeError("redis down")

    # `openbankapi.infra.database.migrations.env`'s `fileConfig(...)` (Alembic)
    # runs with the library default `disable_existing_loggers=True` whenever
    # some earlier test migrates a real database (`db_fixtures.migrate_to_head`)
    # — that permanently disables every module-level logger already created
    # by then, this one included, regardless of `caplog`'s own level/handler.
    # Re-enabling here makes this test order-independent instead of relying
    # on collection order to dodge that pre-existing, unrelated side effect.
    logging.getLogger("openbankapi.status_registry").disabled = False

    async def scenario():
        registry, _ = _registry(RaisingClient())
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)
        with caplog.at_level("ERROR"):
            registry.resolve_threadsafe({"request_id": "r5", "status": "approved"})
            await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert any("resolve failed" in record.message for record in caplog.records)


def test_pending_count_reflects_active_waiters():
    async def scenario():
        registry, _ = _registry()
        assert registry.pending_count() == 0
        task = asyncio.ensure_future(registry.wait_for("r6", timeout=0.3))
        await asyncio.sleep(0.05)
        assert registry.pending_count() == 1
        await task
        assert registry.pending_count() == 0

    asyncio.run(scenario())
