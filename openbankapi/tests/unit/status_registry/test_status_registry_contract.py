"""Shared `IStatusRegistry` contract (Task 1.8) — run against both the
Redis-backed registry (fake client double) and `FakeStatusRegistry`. Proves
the design's parity requirement: "both expose identical method signatures
and both pass the shared contract tests other than the real-Redis-only race
test" (spec's Fake registry satisfies the same interface scenario).

The real subscribe-before-check race itself is real-Redis-only — see
`tests/integration/test_redis_status_registry.py` — deliberately not
duplicated here: a fake's ordering is correct by construction.
"""
from __future__ import annotations

import asyncio

import pytest

from openbankapi.infra.status_registry.repositories.fake_status_registry import (
    FakeStatusRegistry,
)
from openbankapi.infra.status_registry.repositories.redis_status_registry import (
    get_redis_status_registry,
)

from .fake_redis_client import FakeRedisStatusRegistryClient


def _redis_backed():
    return get_redis_status_registry(FakeRedisStatusRegistryClient(), "transfer", 240)


REGISTRY_FACTORIES = [_redis_backed, FakeStatusRegistry]
REGISTRY_IDS = ["redis_backed", "fake"]


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_get_is_none_before_resolve(make_registry):
    async def scenario():
        registry = make_registry()
        assert await registry.get("unseen") is None

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_resolve_then_get_returns_the_event(make_registry):
    async def scenario():
        registry = make_registry()
        await registry.resolve({"request_id": "r1", "status": "approved"})
        assert await registry.get("r1") == {"request_id": "r1", "status": "approved"}

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_wait_for_returns_cached_value(make_registry):
    async def scenario():
        registry = make_registry()
        await registry.resolve({"request_id": "r1", "status": "approved"})
        result = await registry.wait_for("r1", timeout=1.0)
        assert result == {"request_id": "r1", "status": "approved"}

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_wait_for_times_out(make_registry):
    async def scenario():
        registry = make_registry()
        assert await registry.wait_for("never", timeout=0.2) is None

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_wait_for_wakes_on_a_late_resolve(make_registry):
    async def scenario():
        registry = make_registry()

        async def resolve_soon():
            await asyncio.sleep(0.05)
            await registry.resolve({"request_id": "r2", "status": "approved"})

        task = asyncio.ensure_future(resolve_soon())
        result = await registry.wait_for("r2", timeout=2.0)
        await task
        assert result is not None and result["request_id"] == "r2"

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_resolve_ignores_an_event_without_request_id(make_registry):
    async def scenario():
        registry = make_registry()
        await registry.resolve({"status": "approved"})  # no request_id — must not raise

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_resolve_threadsafe_wakes_a_waiter(make_registry):
    async def scenario():
        registry = make_registry()
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)
        task = asyncio.ensure_future(registry.wait_for("r3", timeout=2.0))
        await asyncio.sleep(0.05)
        registry.resolve_threadsafe({"request_id": "r3", "status": "approved"})
        result = await task
        assert result is not None and result["request_id"] == "r3"

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_pending_count_reflects_active_waiters(make_registry):
    async def scenario():
        registry = make_registry()
        assert registry.pending_count() == 0
        task = asyncio.ensure_future(registry.wait_for("r4", timeout=0.3))
        await asyncio.sleep(0.05)
        assert registry.pending_count() >= 1
        await task
        assert registry.pending_count() == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("make_registry", REGISTRY_FACTORIES, ids=REGISTRY_IDS)
def test_a_redelivered_resolve_does_not_overwrite_the_first_verdict(make_registry):
    """At-least-once delivery means the same status can arrive more than
    once — the first one is the one a caller may already have seen."""

    async def scenario():
        registry = make_registry()
        await registry.resolve({"request_id": "r5", "status": "approved"})
        await registry.resolve({"request_id": "r5", "status": "declined"})
        assert (await registry.get("r5"))["status"] == "approved"

    asyncio.run(scenario())
