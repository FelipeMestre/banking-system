"""RED for `PostgresAccountRepository.get_by_id` (Credit Cards Phase 3 —
task 2 prerequisite). `card_accounts.paying_account_id` names an account by
its UUID `id`, not its `account_number`; `IAccountRepository` had no method
to resolve that until now. Real Postgres, no mocking the database (per this
repo's own anti-pattern list) — mirrors `test_card_account_repository.py`'s
`fx_test_dsn`/`rollback_session` pattern.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from openbankapi.infra.database.repositories.postgres_account_repository import (
    PostgresAccountRepository,
)
from openbankapi.infra.database.schemas.models import AccountORM, CustomerORM
from openbankapi.tests.db_fixtures import rollback_session


async def _create_account(dsn: str):
    async with rollback_session(dsn) as session:
        customer = CustomerORM(
            identification_number=f"id-{uuid.uuid4().hex[:16]}",
            first_name="Ada",
            last_name="Lovelace",
            date_of_birth=datetime(1990, 1, 1).date(),
        )
        session.add(customer)
        await session.flush()

        account = AccountORM(
            account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
            currency="EUR",
            customer_id=customer.id,
        )
        session.add(account)
        await session.flush()

        repo = PostgresAccountRepository(session)
        fetched = await repo.get_by_id(account.id)
        missing = await repo.get_by_id(uuid.uuid4())
        return account, fetched, missing


def test_get_by_id_returns_the_matching_account(fx_test_dsn):
    account, fetched, _ = asyncio.run(_create_account(fx_test_dsn))
    assert fetched is not None
    assert fetched.id == account.id
    assert fetched.account_number == account.account_number
    assert fetched.currency == "EUR"


def test_get_by_id_returns_none_for_an_unknown_id(fx_test_dsn):
    _, _, missing = asyncio.run(_create_account(fx_test_dsn))
    assert missing is None
