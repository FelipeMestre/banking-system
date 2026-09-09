"""RED for Credit Cards Phase 1: `PostgresCardRepository` CRUD + collision
retry (T15). Real Postgres via `fx_test_dsn`, mirrors `test_card_account_repository.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_card_repository import (
    PostgresCardRepository,
    generate_card_number,
)
from openbankapi.infra.database.schemas.models import AccountORM, BranchORM, CustomerORM, LocationORM
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card_account(session):
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

    card_account_repo = PostgresCardAccountRepository(session)
    return await card_account_repo.create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=1000
    )


async def _create_card(dsn: str):
    async with rollback_session(dsn) as session:
        card_account = await _seed_card_account(session)
        repo = PostgresCardRepository(session)
        expiration = date.today() + timedelta(days=365 * 4)
        card = await repo.create(card_account_id=card_account.id, expiration_date=expiration)
        by_number = await repo.get_by_number(card.card_number)
        active = await repo.get_active_for_account(card_account.id)
        replaced = await repo.mark_replaced(card.id)
        blocked_new = await repo.create(card_account_id=card_account.id, expiration_date=expiration)
        blocked = await repo.update_status(blocked_new.id, status="blocked")
        return card, by_number, active, replaced, blocked


def test_create_persists_active_card_with_16_digit_number(fx_test_dsn):
    card, by_number, active, replaced, blocked = asyncio.run(_create_card(fx_test_dsn))
    assert len(card.card_number) == 16
    assert card.card_number.isdigit()
    assert card.status.value == "active"


def test_get_by_number_returns_the_created_card(fx_test_dsn):
    card, by_number, active, replaced, blocked = asyncio.run(_create_card(fx_test_dsn))
    assert by_number is not None
    assert by_number.id == card.id


def test_get_active_for_account_returns_the_active_card(fx_test_dsn):
    card, by_number, active, replaced, blocked = asyncio.run(_create_card(fx_test_dsn))
    assert active is not None
    assert active.id == card.id


def test_mark_replaced_transitions_the_card(fx_test_dsn):
    card, by_number, active, replaced, blocked = asyncio.run(_create_card(fx_test_dsn))
    assert replaced is not None
    assert replaced.status.value == "replaced"


def test_update_status_transitions_a_different_card(fx_test_dsn):
    card, by_number, active, replaced, blocked = asyncio.run(_create_card(fx_test_dsn))
    assert blocked is not None
    assert blocked.status.value == "blocked"


async def _collision_retry(dsn: str):
    async with rollback_session(dsn) as session:
        card_account = await _seed_card_account(session)
        repo = PostgresCardRepository(session)
        expiration = date.today() + timedelta(days=365 * 4)

        first = await repo.create(card_account_id=card_account.id, expiration_date=expiration)

        # Force the next two generator calls to collide with the first card's
        # number before finally returning a fresh one — proves the SAVEPOINT
        # retry succeeds without rolling back the outer session.
        sequence = iter([first.card_number, first.card_number, generate_card_number()])
        with patch(
            "openbankapi.infra.database.repositories.postgres_card_repository.generate_card_number",
            side_effect=lambda: next(sequence),
        ):
            second = await repo.create(card_account_id=card_account.id, expiration_date=expiration)

        # The outer session must still be usable after the retried collisions.
        still_readable = await repo.get_by_number(first.card_number)
        return first, second, still_readable


def test_a_card_number_collision_is_retried_within_a_savepoint(fx_test_dsn):
    first, second, still_readable = asyncio.run(_collision_retry(fx_test_dsn))
    assert second.card_number != first.card_number
    assert still_readable is not None
    assert still_readable.id == first.id
