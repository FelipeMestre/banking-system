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
from openbankapi.infra.kafka.status_registry import StatusRegistry


def test_dispatch_resolves_the_payment_registry_only():
    async def scenario():
        registry = StatusRegistry()
        other_registry = StatusRegistry()
        registry.bind_loop(asyncio.get_running_loop())
        consumer = CardPaymentStatusConsumer(Settings(), registry)

        consumer._dispatch(
            json.dumps({"request_id": "req-1", "status": "approved", "ts": "2026-01-01T00:00:00Z"}).encode()
        )
        # `resolve_threadsafe` schedules via `call_soon_threadsafe` — yield once.
        await asyncio.sleep(0)
        return registry.get("req-1"), other_registry.get("req-1")

    resolved, leaked = asyncio.run(scenario())
    assert resolved == {"request_id": "req-1", "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    assert leaked is None


def test_group_id_defaults_to_a_unique_value_when_unconfigured():
    consumer = CardPaymentStatusConsumer(Settings(card_payment_status_consumer_group=""), StatusRegistry())
    first = consumer._group_id()
    second = CardPaymentStatusConsumer(Settings(card_payment_status_consumer_group=""), StatusRegistry())._group_id()
    assert first != second
    assert first.startswith("openbankapi-card-payment-status-")


def test_group_id_uses_the_configured_value_when_present():
    consumer = CardPaymentStatusConsumer(
        Settings(card_payment_status_consumer_group="fixed-group"), StatusRegistry()
    )
    assert consumer._group_id() == "fixed-group"


def test_malformed_record_is_dropped_without_raising():
    consumer = CardPaymentStatusConsumer(Settings(), StatusRegistry())
    consumer._dispatch(b"not json")  # must not raise
    consumer._dispatch(b"")  # must not raise
