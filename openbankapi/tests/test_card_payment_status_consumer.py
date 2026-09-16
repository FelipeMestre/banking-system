"""`CardPaymentStatusConsumer` — translation into its own registry (Credit
Cards Phase 3 — task 13). Mirrors the reasoning `test_card_payment_status_router.py`
establishes: exercises `_dispatch` directly, same convention
`test_transaction_consumer.py` establishes for the thread/poll loop being
plumbing, not the part that can be wrong.
"""
from __future__ import annotations

import asyncio
import json

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.card_payment_status_consumer import CardPaymentStatusConsumer
from openbankapi.infra.status_registry.repositories.fake_status_registry import (
    FakeStatusRegistry,
)


def test_dispatch_resolves_the_payment_registry_only():
    async def scenario():
        registry = FakeStatusRegistry()
        other_registry = FakeStatusRegistry()
        registry.bind_loop(asyncio.get_running_loop())
        consumer = CardPaymentStatusConsumer(Settings(), registry)

        consumer._dispatch(
            json.dumps({"request_id": "req-1", "status": "approved", "ts": "2026-01-01T00:00:00Z"}).encode()
        )
        # `resolve_threadsafe` schedules via `call_soon_threadsafe` -> `ensure_future`
        # -> the task's first step — two loop ticks, not one.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return await registry.get("req-1"), await other_registry.get("req-1")

    resolved, leaked = asyncio.run(scenario())
    assert resolved == {"request_id": "req-1", "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    assert leaked is None


def test_group_id_defaults_to_a_fixed_shared_value():
    # Fixed and shared across every worker instance (horizontal scalability):
    # two instances must land in the same consumer group, or Kafka would hand
    # each one a full duplicate copy of the topic instead of splitting it.
    first = CardPaymentStatusConsumer(Settings(), FakeStatusRegistry())._group_id()
    second = CardPaymentStatusConsumer(Settings(), FakeStatusRegistry())._group_id()
    assert first == second == "openbankapi-card-payment-status"


def test_group_id_uses_the_configured_value_when_present():
    consumer = CardPaymentStatusConsumer(
        Settings(card_payment_status_consumer_group="fixed-group"), FakeStatusRegistry()
    )
    assert consumer._group_id() == "fixed-group"


def test_malformed_record_is_dropped_without_raising():
    consumer = CardPaymentStatusConsumer(Settings(), FakeStatusRegistry())
    consumer._dispatch(b"not json")  # must not raise
    consumer._dispatch(b"")  # must not raise
