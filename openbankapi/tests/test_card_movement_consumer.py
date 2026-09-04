"""`CardMovementConsumer` — event-to-row translation (Credit Cards Phase 2, design §5).

Exercises `_apply` directly, same convention `test_transaction_consumer.py`
establishes: the thread and poll loop are plumbing, the translation logic is
the part that can be wrong.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.card_movement_consumer import CardMovementConsumer

from .fakes import FakeAppliedRateRepository, FakeCardMovementRepository, FakeInstallmentRepository

CARD_ID = str(uuid.uuid4())
CARD_ACCOUNT_ID = str(uuid.uuid4())


def _consumer(movement_repo=None, installment_repo=None, applied_rate_repo=None):
    return CardMovementConsumer(
        Settings(),
        movement_repo or FakeCardMovementRepository(),
        installment_repo or FakeInstallmentRepository(),
        applied_rate_repo,
    )


def _approved(request_id: str, amount_usd: int = 10000, installments: int = 1, applied_rate=None) -> bytes:
    payload = {
        "type": "purchase_approved",
        "request_id": request_id,
        "card_id": CARD_ID,
        "card_account_id": CARD_ACCOUNT_ID,
        "amount_usd": amount_usd,
        "installments": installments,
        "ts": "2026-01-01T00:00:00Z",
    }
    if applied_rate is not None:
        payload["applied_rate"] = applied_rate
    return json.dumps(payload).encode()


def _declined(request_id: str, amount_usd: int = 10000) -> bytes:
    return json.dumps(
        {
            "type": "purchase_declined",
            "request_id": request_id,
            "card_id": CARD_ID,
            "card_account_id": CARD_ACCOUNT_ID,
            "amount_usd": amount_usd,
            "decline_reason": "insufficient_credit",
            "ts": "2026-01-01T00:00:00Z",
        }
    ).encode()


def test_purchase_approved_becomes_a_purchase_movement():
    async def scenario():
        repo = FakeCardMovementRepository()
        await _consumer(repo)._apply(_approved(str(uuid.uuid4())))
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].movement_type.value == "purchase"
    assert rows[0].amount == 100
    assert rows[0].currency == "USD"
    assert str(rows[0].card_id) == CARD_ID


def test_purchase_declined_becomes_a_declined_movement_with_a_reason():
    async def scenario():
        repo = FakeCardMovementRepository()
        await _consumer(repo)._apply(_declined(str(uuid.uuid4())))
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].movement_type.value == "declined"
    assert rows[0].decline_reason == "insufficient_credit"


def test_purchase_requested_is_never_dispatched():
    async def scenario():
        repo = FakeCardMovementRepository()
        payload = json.dumps(
            {
                "type": "purchase_requested", "request_id": str(uuid.uuid4()),
                "card_id": CARD_ID, "card_account_id": CARD_ACCOUNT_ID,
                "amount_usd": 100, "credit_limit": 10000, "ts": "2026-01-01T00:00:00Z",
            }
        ).encode()
        await _consumer(repo)._apply(payload)
        return repo.rows

    assert asyncio.run(scenario()) == []


def test_installments_greater_than_one_splits_into_installment_rows():
    async def scenario():
        movement_repo = FakeCardMovementRepository()
        installment_repo = FakeInstallmentRepository()
        await _consumer(movement_repo, installment_repo)._apply(
            _approved(str(uuid.uuid4()), amount_usd=10000, installments=3)
        )
        return movement_repo.rows, installment_repo.rows

    movement_rows, installment_rows = asyncio.run(scenario())
    assert len(movement_rows) == 1
    assert len(installment_rows) == 3
    assert sum(row.amount for row in installment_rows) == movement_rows[0].amount
    assert [row.installment_number for row in installment_rows] == [1, 2, 3]


def test_single_installment_purchase_never_writes_installment_rows():
    async def scenario():
        movement_repo = FakeCardMovementRepository()
        installment_repo = FakeInstallmentRepository()
        await _consumer(movement_repo, installment_repo)._apply(_approved(str(uuid.uuid4())))
        return installment_repo.rows

    assert asyncio.run(scenario()) == []


def test_applied_rate_is_persisted_and_linked_when_present():
    async def scenario():
        movement_repo = FakeCardMovementRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        await _consumer(movement_repo, applied_rate_repo=applied_rate_repo)._apply(
            _approved(
                str(uuid.uuid4()),
                applied_rate={
                    "pair": "EUR/USD", "mid_rate": 1.1, "applied_rate": 1.08,
                    "margin": 0.02, "direction": "sell", "source_ts": "2026-01-01T00:00:00Z",
                },
            )
        )
        return movement_repo.rows, applied_rate_repo.rows

    movement_rows, applied_rate_rows = asyncio.run(scenario())
    assert len(applied_rate_rows) == 1
    assert movement_rows[0].applied_rate_id == applied_rate_rows[0]["id"]


def test_router_to_domain_to_consumer_pipeline_links_applied_rate_for_real_fx_purchase():
    """True end-to-end regression for the `applied_rate` field-name bug.

    Builds the `purchase_requested` wire event with the EXACT shape
    `card_router.py` publishes (see its `wire` dict), feeds it through the
    REAL `card_domain.decide()` (card-service/domain.py, loaded by
    `card-service/tests/conftest.py` into `sys.modules["card_domain"]` for
    this same pytest session), and asserts the resulting `purchase_approved`
    event carries `applied_rate` and that `CardMovementConsumer` links it to
    an `applied_rates` row.

    Two independently-hand-built fixtures (one for the router's key name,
    one for the consumer's) could silently drift again exactly as they did
    before this fix — this test instead pipes one real event through both
    real functions, so a future rename on either side fails this test.
    """
    import card_domain

    async def scenario():
        applied_rate_quote = {
            "pair": "EUR_USD",
            "mid_rate": 1.1,
            "applied_rate": 1.08,
            "margin": 0.02,
            "direction": "debit",
            "source_ts": "2026-01-01T00:00:00Z",
        }
        # Exact shape of `card_router.py`'s `wire` dict for a foreign-currency
        # purchase: `applied_rate` set to the conversion quote, never a key
        # named `conversion`.
        purchase_requested_event = {
            "type": "purchase_requested",
            "request_id": str(uuid.uuid4()),
            "card_id": CARD_ID,
            "card_account_id": CARD_ACCOUNT_ID,
            "amount": "100.00",
            "currency": "EUR",
            "amount_usd": 10000,
            "credit_limit": 100000,
            "installments": 1,
            "description": None,
            "applied_rate": applied_rate_quote,
            "ts": "2026-01-01T00:00:00Z",
        }

        decision = card_domain.decide(
            card_domain.CardState(used_credit=0, processed=frozenset()),
            purchase_requested_event,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        purchase_approved_event = decision.card_events[0]
        assert purchase_approved_event["type"] == "purchase_approved"
        assert purchase_approved_event["applied_rate"] == applied_rate_quote

        movement_repo = FakeCardMovementRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        await _consumer(movement_repo, applied_rate_repo=applied_rate_repo)._apply(
            json.dumps(purchase_approved_event).encode()
        )
        return movement_repo.rows, applied_rate_repo.rows

    movement_rows, applied_rate_rows = asyncio.run(scenario())
    assert len(applied_rate_rows) == 1
    assert movement_rows[0].applied_rate_id == applied_rate_rows[0]["id"]


def test_redelivering_the_same_approved_event_does_not_duplicate_installments():
    async def scenario():
        movement_repo = FakeCardMovementRepository()
        installment_repo = FakeInstallmentRepository()
        consumer = _consumer(movement_repo, installment_repo)
        payload = _approved(str(uuid.uuid4()), amount_usd=10000, installments=2)
        for _ in range(3):
            await consumer._apply(payload)
        return movement_repo.rows, installment_repo.rows

    movement_rows, installment_rows = asyncio.run(scenario())
    assert len(movement_rows) == 1
    assert len(installment_rows) == 2


def test_a_malformed_record_is_dropped_not_fatal():
    assert CardMovementConsumer._parse(b"not json") is None
    assert CardMovementConsumer._parse(b"") is None
    assert CardMovementConsumer._parse(b"[1, 2]") is None


def test_a_record_missing_required_fields_is_dropped_not_fatal():
    async def scenario():
        repo = FakeCardMovementRepository()
        payload = json.dumps({"type": "purchase_approved", "card_id": CARD_ID}).encode()
        await _consumer(repo)._apply(payload)
        return repo.rows

    assert asyncio.run(scenario()) == []
