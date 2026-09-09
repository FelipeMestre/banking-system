"""`TransactionService.list_for_account` — cursor shaping (spec §3.3)."""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from openbankapi.domain.service.transaction_service import TransactionService
from openbankapi.tests.fakes import FakeTransactionRepository

ACCOUNT = "1111111111111111"
COUNTERPARTY = "2222222222222222"


def _ts(offset_seconds: int = 0) -> dt.datetime:
    return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=offset_seconds)


async def _seed(repo, count: int):
    for i in range(count):
        await repo.insert(
            request_id=uuid.uuid4(), account_number=ACCOUNT, type="credit",
            amount=i, counterparty_account=COUNTERPARTY, decline_reason=None, ts=_ts(i),
        )


def test_first_page_with_no_cursor_returns_newest_first_and_a_next_cursor():
    async def scenario():
        repo = FakeTransactionRepository()
        await _seed(repo, 5)
        service = TransactionService(repo)
        return await service.list_for_account(ACCOUNT, limit=2, cursor=None)

    page = asyncio.run(scenario())
    assert [t.amount for t in page.items] == [4, 3]
    assert page.next_cursor is not None


def test_walking_every_page_with_the_cursor_visits_each_row_exactly_once():
    async def scenario():
        repo = FakeTransactionRepository()
        await _seed(repo, 5)
        service = TransactionService(repo)
        seen = []
        cursor = None
        for _ in range(10):
            page = await service.list_for_account(ACCOUNT, limit=2, cursor=cursor)
            seen.extend(t.amount for t in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        return seen

    assert asyncio.run(scenario()) == [4, 3, 2, 1, 0]


def test_the_last_page_has_no_next_cursor():
    async def scenario():
        repo = FakeTransactionRepository()
        await _seed(repo, 2)
        service = TransactionService(repo)
        return await service.list_for_account(ACCOUNT, limit=10, cursor=None)

    page = asyncio.run(scenario())
    assert page.next_cursor is None


def test_an_account_with_no_transactions_returns_an_empty_page():
    async def scenario():
        repo = FakeTransactionRepository()
        service = TransactionService(repo)
        return await service.list_for_account(ACCOUNT, limit=20, cursor=None)

    page = asyncio.run(scenario())
    assert page.items == []
    assert page.next_cursor is None
