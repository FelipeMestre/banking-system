"""RED/GREEN for task B3: `FakeStatementRepository` round-trip against the
fake only (`create` -> `get_latest` -> `exists_for_period` ->
`finalize_due_date_outcome`)."""
from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal

from openbankapi.tests.fakes import FakeStatementRepository


async def _round_trip():
    repo = FakeStatementRepository()
    card_account_id = uuid.uuid4()

    before = await repo.exists_for_period(card_account_id, date(2026, 9, 20))
    statement = await repo.create(
        card_account_id, date(2026, 8, 20), date(2026, 9, 20), date(2026, 10, 10),
        purchases_total=Decimal("950.00"), interest_total=Decimal("0.00"),
        total_due=Decimal("950.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("25.00"),
    )
    after = await repo.exists_for_period(card_account_id, date(2026, 9, 20))
    latest = await repo.get_latest(card_account_id)

    await repo.finalize_due_date_outcome(
        statement.id, paid_amount=Decimal("950.00"), paid_in_full=True, paid_by_due_date=True
    )
    finalized = await repo.get_latest(card_account_id)
    still_pending = await repo.list_with_due_date(date(2026, 10, 10), outcome_not_finalized=True)

    return before, after, latest, finalized, still_pending


def test_create_get_latest_exists_and_finalize_round_trip():
    before, after, latest, finalized, still_pending = asyncio.run(_round_trip())

    assert before is False
    assert after is True
    assert latest.total_due == Decimal("950.00")
    assert finalized.paid_in_full is True
    assert finalized.paid_by_due_date is True
    assert finalized.status.value == "paid"
    assert still_pending == []


async def _get_by_id_and_list_scenario():
    repo = FakeStatementRepository()
    account_a, account_b = uuid.uuid4(), uuid.uuid4()

    oldest = await repo.create(
        account_a, date(2026, 6, 20), date(2026, 7, 20), date(2026, 8, 10),
        purchases_total=Decimal("100.00"), interest_total=Decimal("0.00"),
        total_due=Decimal("100.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("10.00"),
    )
    newest = await repo.create(
        account_a, date(2026, 7, 20), date(2026, 8, 20), date(2026, 9, 10),
        purchases_total=Decimal("200.00"), interest_total=Decimal("0.00"),
        total_due=Decimal("200.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("20.00"),
    )
    other_account = await repo.create(
        account_b, date(2026, 7, 20), date(2026, 8, 20), date(2026, 9, 10),
        purchases_total=Decimal("999.00"), interest_total=Decimal("0.00"),
        total_due=Decimal("999.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("50.00"),
    )

    found = await repo.get_by_id(oldest.id)
    missing = await repo.get_by_id(uuid.uuid4())
    listed = await repo.list_by_card_account_id(account_a, limit=10)
    capped = await repo.list_by_card_account_id(account_a, limit=1)

    return oldest, newest, other_account, found, missing, listed, capped


def test_get_by_id_and_list_by_card_account_id_against_fake():
    oldest, newest, other_account, found, missing, listed, capped = asyncio.run(
        _get_by_id_and_list_scenario()
    )

    assert found.id == oldest.id
    assert missing is None
    # newest `period_end` first, scoped to the requested account only.
    assert [row.id for row in listed] == [newest.id, oldest.id]
    assert other_account.id not in [row.id for row in listed]
    assert [row.id for row in capped] == [newest.id]
