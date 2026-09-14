"""End-to-end shape test (spec §3.1) — a real transfer and a declined one,
fed through `TransactionConsumer` as the exact `account-events` payloads
`account-service/domain.py`'s builders produce, asserting the resulting rows.

No live Kafka or Postgres: per this repo's convention, the consumer's
`ITransactionRepository` is a fake, and the payloads are literal dicts shaped
exactly like `_outgoing`/`_incoming`/`_declined` (verified against
`account-service/domain.py` on disk) rather than importing that separate,
non-package `account-service/` project.
"""
from __future__ import annotations

import asyncio
import json
import uuid

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer

from .fakes import FakeTransactionRepository

SOURCE = "1111111111111111"
DESTINATION = "2222222222222222"
FEES_ACCOUNT = "0000000000000001"
TS = "2026-01-01T00:00:00.000Z"


def _consumer(repo):
    return TransactionConsumer(Settings(), repo)


def test_a_successful_transfer_with_a_fee_produces_the_correct_debit_and_credit_rows():
    """Amount 1100 + fee 25 from SOURCE to DESTINATION (spec §3.1 scenario)."""
    request_id = str(uuid.uuid4())

    outgoing = {
        "type": "outgoing_payment", "request_id": request_id, "account_id": SOURCE,
        "amount": 1125, "fee_amount": 25, "destination_account": DESTINATION, "leg": "debit", "ts": TS,
    }
    incoming_destination = {
        "type": "incoming_payment", "request_id": request_id, "account_id": DESTINATION,
        "amount": 1100, "source_account": SOURCE, "leg": "credit:destination", "ts": TS,
    }
    incoming_fees = {
        "type": "incoming_payment", "request_id": request_id, "account_id": FEES_ACCOUNT,
        "amount": 25, "source_account": SOURCE, "leg": "credit:fees", "ts": TS,
    }

    async def scenario():
        repo = FakeTransactionRepository()
        consumer = _consumer(repo)
        for event in (outgoing, incoming_destination, incoming_fees):
            await consumer._apply(json.dumps(event).encode())
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 3

    debit = next(r for r in rows if r.account_number == SOURCE)
    assert debit.type.value == "debit"
    assert debit.amount == 1125
    assert debit.counterparty_account == DESTINATION

    destination_credit = next(r for r in rows if r.account_number == DESTINATION)
    assert destination_credit.type.value == "credit"
    assert destination_credit.amount == 1100
    assert destination_credit.counterparty_account == SOURCE

    fees_credit = next(r for r in rows if r.account_number == FEES_ACCOUNT)
    assert fees_credit.type.value == "credit"
    assert fees_credit.amount == 25
    assert fees_credit.counterparty_account == SOURCE


def test_a_declined_transfer_produces_exactly_one_declined_row_with_a_reason():
    request_id = str(uuid.uuid4())
    declined = {
        "type": "declined_payment", "request_id": request_id, "account_id": SOURCE,
        "amount": 1125, "destination_account": DESTINATION, "reason": "insufficient_funds", "ts": TS,
    }

    async def scenario():
        repo = FakeTransactionRepository()
        await _consumer(repo)._apply(json.dumps(declined).encode())
        return repo.rows

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].type.value == "declined"
    assert rows[0].amount == 1125
    assert rows[0].counterparty_account == DESTINATION
    assert rows[0].decline_reason == "insufficient_funds"


def test_redelivering_the_full_transfer_does_not_duplicate_any_leg():
    request_id = str(uuid.uuid4())
    events = [
        {
            "type": "outgoing_payment", "request_id": request_id, "account_id": SOURCE,
            "amount": 1125, "fee_amount": 25, "destination_account": DESTINATION, "ts": TS,
        },
        {
            "type": "incoming_payment", "request_id": request_id, "account_id": DESTINATION,
            "amount": 1100, "source_account": SOURCE, "leg": "credit:destination", "ts": TS,
        },
    ]

    async def scenario():
        repo = FakeTransactionRepository()
        consumer = _consumer(repo)
        for _ in range(2):  # simulate at-least-once redelivery of the whole batch
            for event in events:
                await consumer._apply(json.dumps(event).encode())
        return repo.rows

    assert len(asyncio.run(scenario())) == 2
