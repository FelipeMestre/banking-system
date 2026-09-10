"""RED for task B4: `PostgresStatementRepository` against real Postgres.
Mirrors `test_postgres_card_movement_and_installment_repository.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_statement_repository import (
    PostgresStatementRepository,
)
from openbankapi.infra.database.schemas.models import AccountORM, CustomerORM
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card_account(session):
    customer = CustomerORM(
        identification_number=f"id-{uuid.uuid4().hex[:16]}",
        first_name="Ada", last_name="Lovelace", date_of_birth=datetime(1990, 1, 1).date(),
    )
    session.add(customer)
    await session.flush()
    account = AccountORM(
        account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
        currency="USD", customer_id=customer.id,
    )
    session.add(account)
    await session.flush()
    return await PostgresCardAccountRepository(session).create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=1000
    )


async def _exercise(dsn: str):
    async with rollback_session(dsn) as session:
        card_account = await _seed_card_account(session)
        repo = PostgresStatementRepository(session)

        before = await repo.exists_for_period(card_account.id, date(2026, 9, 20))
        statement = await repo.create(
            card_account.id, date(2026, 8, 20), date(2026, 9, 20), date(2026, 10, 10),
            purchases_total=Decimal("950.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("950.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("25.00"),
        )
        after = await repo.exists_for_period(card_account.id, date(2026, 9, 20))
        latest = await repo.get_latest(card_account.id)

        pending_before = await repo.list_with_due_date(date(2026, 10, 10), outcome_not_finalized=True)
        await repo.finalize_due_date_outcome(
            statement.id, paid_amount=Decimal("950.00"), paid_in_full=True, paid_by_due_date=True
        )
        pending_after = await repo.list_with_due_date(date(2026, 10, 10), outcome_not_finalized=True)
        finalized = await repo.get_latest(card_account.id)

        return before, after, latest, pending_before, pending_after, finalized


def test_statement_repository_full_round_trip(fx_test_dsn):
    before, after, latest, pending_before, pending_after, finalized = asyncio.run(
        _exercise(fx_test_dsn)
    )

    assert before is False
    assert after is True
    assert latest.total_due == Decimal("950.00")
    assert len(pending_before) == 1
    assert pending_after == []
    assert finalized.paid_in_full is True
    assert finalized.status.value == "paid"


async def _exercise_get_by_id_and_list(dsn: str):
    async with rollback_session(dsn) as session:
        account = await _seed_card_account(session)
        repo = PostgresStatementRepository(session)

        older = await repo.create(
            account.id, date(2026, 6, 20), date(2026, 7, 20), date(2026, 8, 10),
            purchases_total=Decimal("100.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("100.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("10.00"),
        )
        newer = await repo.create(
            account.id, date(2026, 7, 20), date(2026, 8, 20), date(2026, 9, 10),
            purchases_total=Decimal("200.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("200.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("20.00"),
        )

        found = await repo.get_by_id(older.id)
        missing = await repo.get_by_id(uuid.uuid4())
        listed = await repo.list_by_card_account_id(account.id, limit=10)
        capped = await repo.list_by_card_account_id(account.id, limit=1)
        return older, newer, found, missing, listed, capped


def test_get_by_id_and_list_by_card_account_id_against_postgres(fx_test_dsn):
    older, newer, found, missing, listed, capped = asyncio.run(
        _exercise_get_by_id_and_list(fx_test_dsn)
    )

    assert found.id == older.id
    assert missing is None
    assert [row.id for row in listed] == [newer.id, older.id]
    assert [row.id for row in capped] == [newer.id]
