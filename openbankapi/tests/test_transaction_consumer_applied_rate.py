"""RED for FX-19: `TransactionConsumer` applied-rate linkage.

`conversion` lives on `incoming_payment` events only (attached by
`account-service/domain.py`'s `_incoming`, FX-18); `outgoing_payment` and
`declined_payment` never carry it and must always link `applied_rate_id=None`.
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

CONVERSION = {
    "pair": "EUR_USD",
    "mid_rate": 1.1628,
    "applied_rate": 1.1512,
    "margin": 0.01,
    "direction": "credit",
    "source_ts": "2026-09-03T12:00:00+00:00",
}


def _consumer(repo, applied_rate_repo):
    return TransactionConsumer(Settings(), repo, applied_rate_repository=applied_rate_repo)


def _incoming_with_conversion(request_id: str, conversion=None, amount: int = 1074) -> bytes:
    payload = {
        "type": "incoming_payment", "request_id": request_id, "account_id": ACCOUNT_B,
        "amount": amount, "source_account": ACCOUNT_A, "ts": "2026-01-01T00:00:00Z",
    }
    if conversion is not None:
        payload["conversion"] = conversion
    return json.dumps(payload).encode()


def _outgoing(request_id: str, amount: int = 1125, fee_amount: int = 25, conversion=None) -> bytes:
    payload = {
        "type": "outgoing_payment", "request_id": request_id, "account_id": ACCOUNT_A,
        "amount": amount, "fee_amount": fee_amount, "destination_account": ACCOUNT_B, "ts": "2026-01-01T00:00:00Z",
    }
    if conversion is not None:
        payload["conversion"] = conversion
    return json.dumps(payload).encode()


def _declined(request_id: str, amount: int = 1125) -> bytes:
    return json.dumps({
        "type": "declined_payment", "request_id": request_id, "account_id": ACCOUNT_A,
        "amount": amount, "destination_account": ACCOUNT_B, "reason": "insufficient_funds",
        "ts": "2026-01-01T00:00:00Z",
    }).encode()


def test_conversion_present_links_a_new_applied_rate_row():
    async def scenario():
        repo = FakeTransactionRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        await _consumer(repo, applied_rate_repo)._apply(
            _incoming_with_conversion(str(uuid.uuid4()), conversion=CONVERSION)
        )
        return repo.rows, applied_rate_repo.rows

    rows, applied_rate_rows = asyncio.run(scenario())
    assert len(applied_rate_rows) == 1
    assert applied_rate_rows[0]["pair"] == "EUR_USD"
    assert rows[0].applied_rate_id == applied_rate_rows[0]["id"]


def test_conversion_absent_links_nothing():
    async def scenario():
        repo = FakeTransactionRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        await _consumer(repo, applied_rate_repo)._apply(
            _incoming_with_conversion(str(uuid.uuid4()))
        )
        return repo.rows, applied_rate_repo.rows

    rows, applied_rate_rows = asyncio.run(scenario())
    assert applied_rate_rows == []
    assert rows[0].applied_rate_id is None


def test_outgoing_and_declined_rows_never_link():
    async def scenario():
        repo = FakeTransactionRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        consumer = _consumer(repo, applied_rate_repo)
        await consumer._apply(_outgoing(str(uuid.uuid4())))
        await consumer._apply(_declined(str(uuid.uuid4())))
        return repo.rows, applied_rate_repo.rows

    rows, applied_rate_rows = asyncio.run(scenario())
    assert applied_rate_rows == []
    assert all(row.applied_rate_id is None for row in rows)


def test_outgoing_and_declined_rows_never_link_REGRESSION_baseline():
    """REGRESSION (Credit Cards Phase 3 — task 10): identical setup and
    assertion to `test_outgoing_and_declined_rows_never_link` above, run again
    to pin down that ordinary transfers' credit-leg linkage behavior is
    UNCHANGED by the widened gate — an ordinary `outgoing_payment` never
    carries `conversion`, so the widened check (`conversion is not None`) is
    a strict no-op for every existing transfer, exactly as design predicted."""
    async def scenario():
        repo = FakeTransactionRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        consumer = _consumer(repo, applied_rate_repo)
        await consumer._apply(_outgoing(str(uuid.uuid4())))
        await consumer._apply(_declined(str(uuid.uuid4())))
        return repo.rows, applied_rate_repo.rows

    rows, applied_rate_rows = asyncio.run(scenario())
    assert applied_rate_rows == []
    assert all(row.applied_rate_id is None for row in rows)


def test_cross_currency_payment_debit_leg_links_applied_rate():
    """NEW (Credit Cards Phase 3 — task 10, applied-rate-debit-linkage): a
    cross-currency card payment's DEBIT-leg `outgoing_payment` event, when it
    carries `conversion` (attached by `account-service/domain.py`'s widened
    `_outgoing()`), now correctly links `applied_rate_id` to a real
    `applied_rates` row — the FIRST precedent for debit-side linkage in this
    codebase."""
    debit_conversion = {
        "pair": "EUR_USD",
        "mid_rate": 1.1628,
        "applied_rate": 1.1512,
        "margin": 0.01,
        "direction": "debit",
        "source_ts": "2026-09-03T12:00:00+00:00",
    }

    async def scenario():
        repo = FakeTransactionRepository()
        applied_rate_repo = FakeAppliedRateRepository()
        await _consumer(repo, applied_rate_repo)._apply(
            _outgoing(str(uuid.uuid4()), conversion=debit_conversion)
        )
        return repo.rows, applied_rate_repo.rows

    rows, applied_rate_rows = asyncio.run(scenario())
    assert len(applied_rate_rows) == 1
    assert applied_rate_rows[0]["direction"] == "debit"
    assert rows[0].applied_rate_id == applied_rate_rows[0]["id"]


def test_missing_applied_rate_repository_still_inserts_transaction_with_none():
    """Backward-compat: an existing caller that never wires the new
    dependency (`applied_rate_repository` defaults to `None`) must not
    break — it simply never links."""
    async def scenario():
        repo = FakeTransactionRepository()
        consumer = TransactionConsumer(Settings(), repo)
        await consumer._apply(_incoming_with_conversion(str(uuid.uuid4()), conversion=CONVERSION))
        return repo.rows

    rows = asyncio.run(scenario())
    assert rows[0].applied_rate_id is None
