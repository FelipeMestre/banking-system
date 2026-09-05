"""RED for Credit Cards Phase 2 (task 1.1): `card_movements` gains `request_id`,
`decline_reason`, and a `'declined'` movement_type, plus the
`(request_id, movement_type)` uniqueness that makes consumer inserts idempotent.
Real Postgres via `fx_test_dsn`, mirrors `test_credit_card_migration.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import text

from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_card_repository import PostgresCardRepository
from openbankapi.infra.database.schemas.models import AccountORM, BranchORM, CustomerORM, LocationORM
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card(session):
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
    card_account = await PostgresCardAccountRepository(session).create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=1000
    )
    card = await PostgresCardRepository(session).create(
        card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
    )
    return card


async def _insert_declined_row(dsn: str):
    async with rollback_session(dsn) as session:
        card = await _seed_card(session)
        request_id = uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO card_movements "
                "(card_id, request_id, movement_type, decline_reason, amount, currency) "
                "VALUES (:card_id, :request_id, 'declined', 'insufficient_credit', 100.00, 'USD')"
            ),
            {"card_id": card.id, "request_id": request_id},
        )
        await session.flush()
        # Idempotent redelivery: same (request_id, movement_type) must not raise.
        result = await session.execute(
            text(
                "INSERT INTO card_movements "
                "(card_id, request_id, movement_type, decline_reason, amount, currency) "
                "VALUES (:card_id, :request_id, 'declined', 'insufficient_credit', 100.00, 'USD') "
                "ON CONFLICT (request_id, movement_type) DO NOTHING"
            ),
            {"card_id": card.id, "request_id": request_id},
        )
        await session.flush()
        count = await session.scalar(
            text("SELECT count(*) FROM card_movements WHERE request_id = :rid"),
            {"rid": request_id},
        )
        return count


def test_declined_movement_type_and_decline_reason_are_accepted_and_deduped(fx_test_dsn):
    count = asyncio.run(_insert_declined_row(fx_test_dsn))
    assert count == 1
