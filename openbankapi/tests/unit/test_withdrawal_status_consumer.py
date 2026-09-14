"""RED for WithdrawalStatusConsumer dispatch — mirrors test_deposit_status_consumer.py."""
import asyncio
import json


def test_withdrawal_status_consumer_dispatch_resolves_registry():
    import asyncio

    from openbankapi.config import Settings
    from openbankapi.infra.kafka.consumers.withdrawal_status_consumer import (
        WithdrawalStatusConsumer,
    )
    from openbankapi.infra.kafka.status_registry import StatusRegistry

    async def scenario():
        settings = Settings(
            withdrawal_status_topic="withdrawal-status",
            withdrawal_status_consumer_group="test-group",
        )
        registry = StatusRegistry(max_cached=10_000)
        loop = asyncio.get_running_loop()
        registry.bind_loop(loop)
        consumer = WithdrawalStatusConsumer(settings, registry)
        assert "test-group" in consumer._group_id() or "openbankapi-withdrawal-status" in consumer._group_id()

        raw = json.dumps({"request_id": "r1", "status": "approved", "new_balance": 54460}).encode()
        consumer._dispatch(raw)
        await asyncio.sleep(0.05)
        result = await registry.wait_for("r1", timeout=0.5)
        assert result is not None
        assert result["new_balance"] == 54460

        assert consumer._settings.withdrawal_status_topic == "withdrawal-status"

    asyncio.run(scenario())


def test_withdrawal_status_consumer_config():
    from openbankapi.config import Settings

    s = Settings()
    assert hasattr(s, "withdrawal_status_topic")
    assert s.withdrawal_status_topic == "withdrawal-status"
    assert hasattr(s, "withdrawal_status_consumer_group")


def test_consumer_has_correct_offsets_and_poll():
    import inspect

    from openbankapi.infra.kafka.consumers.withdrawal_status_consumer import (
        WithdrawalStatusConsumer,
    )

    src = inspect.getsource(WithdrawalStatusConsumer._run)
    assert 'enable.auto.commit' in src
    assert 'False' in src
    assert 'earliest' in src
    assert 'poll(0.5)' in src or 'poll' in src
