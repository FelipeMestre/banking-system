"""`ITransactionRepository` behaviour exercised through the fake (spec §3.2).

No live Postgres here, per this repo's convention: `FakeTransactionRepository`
is the same in-memory double every other repository test uses.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from openbankapi.tests.fakes import FakeTransactionRepository

ACCOUNT_A = "1111111111111111"
ACCOUNT_B = "2222222222222222"


def _ts(offset_seconds: int = 0) -> dt.datetime:
    return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=offset_seconds)


def test_insert_is_idempotent_on_redelivery():
    async def scenario():
        repo = FakeTransactionRepository()
        request_id = uuid.uuid4()
        for _ in range(3):
            await repo.insert(
                request_id=request_id, account_number=ACCOUNT_A, type="debit",
                amount=1125, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(),
            )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].amount == 1125


def test_insert_accepts_and_persists_an_applied_rate_id():
    rate_id = uuid.uuid4()

    async def scenario():
        repo = FakeTransactionRepository()
        await repo.insert(
            request_id=uuid.uuid4(), account_number=ACCOUNT_A, type="credit",
            amount=1074, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(),
            applied_rate_id=rate_id,
        )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert rows[0].applied_rate_id == rate_id


def test_insert_defaults_applied_rate_id_to_none():
    async def scenario():
        repo = FakeTransactionRepository()
        await repo.insert(
            request_id=uuid.uuid4(), account_number=ACCOUNT_A, type="debit",
            amount=1125, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(),
        )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert rows[0].applied_rate_id is None


def test_a_different_type_for_the_same_request_and_account_is_a_distinct_row():
    """`(request_id, account_number, type)` is the identity — not just `request_id`."""
    async def scenario():
        repo = FakeTransactionRepository()
        request_id = uuid.uuid4()
        await repo.insert(
            request_id=request_id, account_number=ACCOUNT_A, type="debit",
            amount=1125, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(),
        )
        await repo.insert(
            request_id=request_id, account_number=ACCOUNT_A, type="credit",
            amount=1125, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(1),
        )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert len(rows) == 2


def test_list_by_account_orders_newest_first():
    async def scenario():
        repo = FakeTransactionRepository()
        for i in range(3):
            await repo.insert(
                request_id=uuid.uuid4(), account_number=ACCOUNT_A, type="credit",
                amount=100 + i, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(i),
            )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert [row.amount for row in rows] == [102, 101, 100]


def test_list_by_account_keyset_pagination_has_no_skip_or_repeat():
    async def scenario():
        repo = FakeTransactionRepository()
        for i in range(5):
            await repo.insert(
                request_id=uuid.uuid4(), account_number=ACCOUNT_A, type="credit",
                amount=i, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(i),
            )
        page1 = await repo.list_by_account(ACCOUNT_A, limit=2)
        last = page1[-1]
        page2 = await repo.list_by_account(ACCOUNT_A, limit=2, before=(last.ts, last.id))
        last2 = page2[-1]
        page3 = await repo.list_by_account(ACCOUNT_A, limit=2, before=(last2.ts, last2.id))
        return [row.amount for page in (page1, page2, page3) for row in page]

    assert asyncio.run(scenario()) == [4, 3, 2, 1, 0]


def test_list_by_account_only_returns_that_accounts_rows():
    async def scenario():
        repo = FakeTransactionRepository()
        await repo.insert(
            request_id=uuid.uuid4(), account_number=ACCOUNT_A, type="debit",
            amount=1, counterparty_account=ACCOUNT_B, decline_reason=None, ts=_ts(),
        )
        await repo.insert(
            request_id=uuid.uuid4(), account_number=ACCOUNT_B, type="credit",
            amount=2, counterparty_account=ACCOUNT_A, decline_reason=None, ts=_ts(1),
        )
        return await repo.list_by_account(ACCOUNT_A, limit=10)

    rows = asyncio.run(scenario())
    assert len(rows) == 1
    assert rows[0].account_number == ACCOUNT_A
