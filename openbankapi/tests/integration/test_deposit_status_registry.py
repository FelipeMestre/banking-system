"""RED for Task 2.1 — DepositStatusRegistry alias + behavior."""
import asyncio
import pytest

from openbankapi.infra.kafka.status_registry import StatusRegistry, DepositStatusRegistry


def test_alias_is_same_class():
    assert DepositStatusRegistry is StatusRegistry


def test_wait_for_timeout_returns_none():
    async def scenario():
        registry = StatusRegistry(max_cached=10_000)
        registry.bind_loop(asyncio.get_running_loop())
        result = await registry.wait_for("xyz-no-resolve", timeout=0.2)
        assert result is None

    asyncio.run(scenario())


def test_resolve_threadsafe_wakes_waiter():
    async def scenario():
        registry = StatusRegistry(max_cached=10_000)
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)
        # start waiter
        task = asyncio.create_task(registry.wait_for("xyz", timeout=2.0))
        await asyncio.sleep(0.05)
        registry.resolve_threadsafe({"request_id": "xyz", "status": "approved", "new_balance": 150000})
        result = await task
        assert result is not None
        assert result["request_id"] == "xyz"
        assert result["status"] == "approved"
        assert result["new_balance"] == 150000

    asyncio.run(scenario())


def test_max_cached_and_get():
    registry = DepositStatusRegistry(max_cached=2)
    loop = asyncio.new_event_loop()
    registry.bind_loop(loop)
    registry.resolve({"request_id": "a", "status": "approved", "new_balance": 100})
    registry.resolve({"request_id": "b", "status": "approved", "new_balance": 200})
    registry.resolve({"request_id": "c", "status": "approved", "new_balance": 300})
    # max_cached 2 -> oldest evicted
    assert registry.get("a") is None
    assert registry.get("c") is not None
    loop.close()
