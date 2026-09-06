"""RED for Task 2.3 — DepositStatusConsumer dispatch."""
import asyncio
import json


def test_deposit_status_consumer_dispatch_resolves_registry():
    import asyncio

    from openbankapi.config import Settings
    from openbankapi.infra.kafka.consumers.deposit_status_consumer import DepositStatusConsumer
    from openbankapi.infra.kafka.status_registry import StatusRegistry

    async def scenario():
        settings = Settings(deposit_status_topic="deposit-status", deposit_status_consumer_group="test-group")
        registry = StatusRegistry(max_cached=10_000)
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)
        consumer = DepositStatusConsumer(settings, registry)
        # check group id is unique per process when empty, but respects configured
        assert "test-group" in consumer._group_id() or "openbankapi-deposit-status" in consumer._group_id()

        # dispatch raw JSON
        raw = json.dumps({"request_id": "r1", "status": "approved", "new_balance": 145540}).encode()
        consumer._dispatch(raw)
        # give loop a chance to run call_soon_threadsafe
        await asyncio.sleep(0.05)
        result = await registry.wait_for("r1", timeout=0.5)
        assert result is not None
        assert result["new_balance"] == 145540

        # consumer must have correct Kafka config
        assert consumer._settings.deposit_status_topic == "deposit-status"

    asyncio.run(scenario())


def test_deposit_status_consumer_config():
    from openbankapi.config import Settings

    s = Settings()
    assert hasattr(s, "deposit_status_topic")
    assert s.deposit_status_topic == "deposit-status"
    assert hasattr(s, "deposit_status_consumer_group")


def test_consumer_has_correct_offsets_and_poll():
    import inspect

    from openbankapi.infra.kafka.consumers.deposit_status_consumer import DepositStatusConsumer

    src = inspect.getsource(DepositStatusConsumer._run)
    assert 'enable.auto.commit' in src
    assert 'False' in src
    assert 'earliest' in src
    assert 'poll(0.5)' in src or 'poll' in src
