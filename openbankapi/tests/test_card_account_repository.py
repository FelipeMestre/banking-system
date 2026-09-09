"""RED for Credit Cards Phase 1: `PostgresCardAccountRepository` CRUD (T13).

Real Postgres via the shared `fx_test_dsn` fixture, no mocking the database
(per this repo's own documented testing anti-pattern list) — mirrors
`test_applied_rate_repository.py`. Uses `rollback_session` so no test leaves
a row behind for the next one.

Environment note: same real-Postgres requirement as the other DB-backed
tests in this suite — see `test_credit_card_migration.py`'s module docstring.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal

from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.schemas.models import AccountORM, CustomerORM
from openbankapi.tests.db_fixtures import rollback_session


async def _create_card_account(dsn: str):
    async with rollback_session(dsn) as session:
        from openbankapi.infra.database.schemas.models import BranchORM, LocationORM

        location = LocationORM(name=f"loc-{uuid.uuid4()}")
        session.add(location)
        await session.flush()
        branch = BranchORM(code=f"B{uuid.uuid4().hex[:8]}", name="Branch", location_id=location.id)
        session.add(branch)
        await session.flush()

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
            currency="USD",
            customer_id=customer.id,
            branch_id=branch.id,
        )
        session.add(account)
        await session.flush()

        repo = PostgresCardAccountRepository(session)
        created = await repo.create(
            customer_id=customer.id, paying_account_id=account.id, credit_limit=Decimal("1000.00")
        )
        fetched = await repo.get_by_id(created.id)
        page = await repo.list_by_customer(customer.id, limit=10, offset=0)
        blocked = await repo.update_status(created.id, status="blocked")
        raised = await repo.update_limit(created.id, credit_limit=Decimal("2000.00"))
        return created, fetched, page, blocked, raised


def test_create_persists_active_card_account_with_credit_limit(fx_test_dsn):
    created, fetched, page, blocked, raised = asyncio.run(_create_card_account(fx_test_dsn))
    assert created.status.value == "active"
    assert created.credit_limit == Decimal("1000.00")
    assert fetched is not None
    assert fetched.id == created.id


def test_list_by_customer_returns_the_created_row(fx_test_dsn):
    created, fetched, page, blocked, raised = asyncio.run(_create_card_account(fx_test_dsn))
    assert page.total == 1
    assert page.items[0].id == created.id


def test_update_status_transitions_the_row(fx_test_dsn):
    created, fetched, page, blocked, raised = asyncio.run(_create_card_account(fx_test_dsn))
    assert blocked is not None
    assert blocked.status.value == "blocked"


def test_update_limit_changes_the_credit_limit(fx_test_dsn):
    created, fetched, page, blocked, raised = asyncio.run(_create_card_account(fx_test_dsn))
    assert raised is not None
    assert raised.credit_limit == Decimal("2000.00")
