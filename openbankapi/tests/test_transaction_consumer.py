"""`TransactionConsumer` — event-to-row translation (spec §3.1, §3.2).

Exercises `_apply` and `_parse` directly, same convention as
`test_balance_consumer.py`: the thread and poll loop are plumbing, the
translation logic is the part that can be wrong.
"""
from __future__ import annotations

import asyncio
import json
import uuid

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer

from .fakes import FakeAppliedRateRepository, FakeTransactionRepository

ACCOUNT_A = "1111111111111111"
ACCOUNT_B = "2222222222222222"


def _consumer(repo):
    return TransactionConsumer(Settings(), repo)


def _outgoing(request_id: str, amount: int = 1125, fee_amount: int = 25) -> bytes:
    return json.dumps({
        "type": "outgoing_payment", "request_id": request_id, "account_id": ACCOUNT_A,
        "amount": amount, "fee_amount": fee_amount, "destination_account": ACCOUNT_B, "ts": "2026-01-01T00:00:00Z",
    }).encode()


def _incoming(request_id: str, amount: int = 1100) -> bytes:
    return json.dumps({
        "type": "incoming_payment", "request_id": request_id, "account_id": ACCOUNT_B,
        "amount": amount, "source_account": ACCOUNT_A, "ts": "2026-01-01T00:00:00Z",
    }).encode()


def _declined(request_id: str, amount: int = 1125) -> bytes:
    return json.dumps({
        "type": "declined_payment", "request_id": request_id, "account_id": ACCOUNT_A,
        "amount": amount, "destination_account": ACCOUNT_B, "reason": "insufficient_funds",
        "ts": "2026-01-01T00:00:00Z",
    }).encode()


# --- dispatch -----------------------------------------------------------------


def test_outgoing_payment_becomes_a_debit_row():
    async def scenario():
        repo = FakeTransactionRepository()
        await _consumer(repo)._apply(_outgoing(str(uuid.uuid4())))
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].type.value == "debit"
    assert rows[0].amount == 1125
    assert rows[0].counterparty_account == ACCOUNT_B
    assert rows[0].account_number == ACCOUNT_A


def test_incoming_payment_becomes_a_credit_row():
    async def scenario():
        repo = FakeTransactionRepository()
        await _consumer(repo)._apply(_incoming(str(uuid.uuid4())))
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].type.value == "credit"
    assert rows[0].counterparty_account == ACCOUNT_A
    assert rows[0].account_number == ACCOUNT_B


def test_declined_payment_becomes_a_declined_row_with_a_reason():
    async def scenario():
        repo = FakeTransactionRepository()
        await _consumer(repo)._apply(_declined(str(uuid.uuid4())))
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].type.value == "declined"
    assert rows[0].decline_reason == "insufficient_funds"


def test_transfer_requested_is_never_dispatched():
    async def scenario():
        repo = FakeTransactionRepository()
        payload = json.dumps({
            "type": "transfer_requested", "request_id": str(uuid.uuid4()),
            "source_account": ACCOUNT_A, "destination_account": ACCOUNT_B,
            "amount": 1100, "fee_amount": 25, "ts": "2026-01-01T00:00:00Z",
        }).encode()
        await _consumer(repo)._apply(payload)
        return repo.rows

    assert asyncio.run(scenario()) == []


# --- idempotency and resilience ------------------------------------------------


def test_redelivering_the_same_event_does_not_duplicate():
    async def scenario():
        repo = FakeTransactionRepository()
        consumer = _consumer(repo)
        payload = _outgoing(str(uuid.uuid4()))
        for _ in range(3):
            await consumer._apply(payload)
        return repo.rows

    assert len(asyncio.run(scenario())) == 1


def test_a_malformed_record_is_dropped_not_fatal():
    assert TransactionConsumer._parse(b"not json") is None
    assert TransactionConsumer._parse(b"") is None
    assert TransactionConsumer._parse(b"[1, 2]") is None


def test_a_record_missing_required_fields_is_dropped_not_fatal():
    async def scenario():
        repo = FakeTransactionRepository()
        payload = json.dumps({"type": "outgoing_payment", "account_id": ACCOUNT_A}).encode()
        await _consumer(repo)._apply(payload)
        return repo.rows

    assert asyncio.run(scenario()) == []
