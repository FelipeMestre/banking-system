"""Tests for the in-process transfer-status fan-out (spec §6)."""
import asyncio
from gateway.status_registry import StatusRegistry

APPROVED = {"request_id": "req-1", "status": "approved", "account_id": "acc-1", "ts": "t"}


def test_unknown_request_is_unresolved():
    assert StatusRegistry().get("req-1") is None


def test_resolved_status_is_cached():
    registry = StatusRegistry()
    registry.resolve(APPROVED)
    assert registry.get("req-1") == APPROVED


def test_wait_returns_immediately_on_a_cache_hit():
    async def scenario():
        registry = StatusRegistry()
        registry.resolve(APPROVED)
        return await registry.wait_for("req-1", timeout=0.01)

    assert asyncio.run(scenario()) == APPROVED


def test_wait_is_woken_by_a_later_status_event():
    async def scenario():
        registry = StatusRegistry()
        waiter = asyncio.ensure_future(registry.wait_for("req-1", timeout=1))
        await asyncio.sleep(0)
        registry.resolve(APPROVED)
        return await waiter

    assert asyncio.run(scenario()) == APPROVED


def test_wait_times_out_to_none():
    async def scenario():
        return await StatusRegistry().wait_for("req-1", timeout=0.01)

    assert asyncio.run(scenario()) is None


def test_every_waiter_on_the_same_request_is_notified():
    async def scenario():
        registry = StatusRegistry()
        waiters = [asyncio.ensure_future(registry.wait_for("req-1", timeout=1)) for _ in range(3)]
        await asyncio.sleep(0)
        registry.resolve(APPROVED)
        return await asyncio.gather(*waiters)

    assert asyncio.run(scenario()) == [APPROVED] * 3


def test_a_timed_out_waiter_does_not_leak():
    async def scenario():
        registry = StatusRegistry()
        await registry.wait_for("req-1", timeout=0.01)
        return registry.pending_count()

    assert asyncio.run(scenario()) == 0


def test_the_cache_is_bounded():
    registry = StatusRegistry(max_cached=2)
    for i in range(3):
        registry.resolve({"request_id": f"req-{i}", "status": "approved"})

    assert registry.get("req-0") is None
    assert registry.get("req-2") is not None


def test_the_first_status_for_a_request_wins():
    registry = StatusRegistry()
    registry.resolve(APPROVED)
    registry.resolve({"request_id": "req-1", "status": "declined"})
    assert registry.get("req-1")["status"] == "approved"
