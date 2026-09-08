"""Integration coverage for Task 5.2: real-Postgres parity for the balance
SQL and the status-filtered listing, plus the audit repository's same-UoW
write. Mirrors `test_postgres_card_movement_and_installment_repository.py`'s
`rollback_session` convention — real Postgres via `fx_test_dsn`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.infra.database.repositories.postgres_card_account_admin_action_repository import (
    PostgresCardAccountAdminActionRepository,
)
from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_card_movement_repository import (
    PostgresCardMovementRepository,
)
from openbankapi.infra.database.repositories.postgres_card_repository import (
    PostgresCardRepository,
)
from openbankapi.infra.database.schemas.models import (
    AccountORM,
    BranchORM,
    CustomerORM,
    LocationORM,
)
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card_account(session, *, credit_limit=1000):
    location = LocationORM(name=f"loc-{uuid.uuid4()}")
    session.add(location)
    await session.flush()
    branch = BranchORM(code=f"B{uuid.uuid4().hex[:8]}", name="Branch", location_id=location.id)
    session.add(branch)
    await session.flush()
    customer = CustomerORM(
        identification_number=f"id-{uuid.uuid4().hex[:16]}",
        first_name="Ada", last_name="Lovelace", date_of_birth=datetime(1990, 1, 1).date(),
    )
    session.add(customer)
    await session.flush()
    account = AccountORM(
        account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
        currency="USD", customer_id=customer.id, branch_id=branch.id,
    )
    session.add(account)
    await session.flush()
    card_account = await PostgresCardAccountRepository(session).create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=credit_limit
    )
    card = await PostgresCardRepository(session).create(
        card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
    )
    return customer, card_account, card


async def _insert(movement_repo, card_id, movement_type, amount):
    await movement_repo.insert(
        CardMovement(
            id=uuid.uuid4(), card_id=card_id, request_id=uuid.uuid4(),
            movement_type=movement_type, amount=Decimal(amount), currency="USD",
            created_at=datetime.now(timezone.utc), occurred_at=datetime.now(timezone.utc),
        )
    )


def _manual_balance(movements: list[tuple[CardMovementType, str]]) -> Decimal:
    increases = {
        CardMovementType.PURCHASE, CardMovementType.FEE, CardMovementType.INTEREST, CardMovementType.LATE_FEE
    }
    decreases = {CardMovementType.PAYMENT, CardMovementType.REFUND}
    total = Decimal(0)
    for movement_type, amount in movements:
        if movement_type in increases:
            total += Decimal(amount)
        elif movement_type in decreases:
            total -= Decimal(amount)
    return total


async def _balance_parity(dsn: str):
    movements = [
        (CardMovementType.PURCHASE, "100.00"),
        (CardMovementType.PAYMENT, "20.00"),
        (CardMovementType.LATE_FEE, "35.00"),
        (CardMovementType.INTEREST, "5.50"),
        (CardMovementType.REFUND, "10.00"),
    ]
    async with rollback_session(dsn) as session:
        _, card_account, card = await _seed_card_account(session)
        movement_repo = PostgresCardMovementRepository(session)
        for movement_type, amount in movements:
            await _insert(movement_repo, card.id, movement_type, amount)

        sql_balance = await movement_repo.compute_current_balance(card_account.id)
        return sql_balance, _manual_balance(movements)


def test_compute_current_balance_matches_manual_sum_over_real_postgres(fx_test_dsn):
    sql_balance, manual_balance = asyncio.run(_balance_parity(fx_test_dsn))
    assert sql_balance == manual_balance
    assert sql_balance == Decimal("110.50")  # 100 - 20 + 35 + 5.50 - 10


async def _no_movements_balance(dsn: str):
    async with rollback_session(dsn) as session:
        _, card_account, _card = await _seed_card_account(session)
        movement_repo = PostgresCardMovementRepository(session)
        return await movement_repo.compute_current_balance(card_account.id)


def test_compute_current_balance_is_zero_with_no_movements(fx_test_dsn):
    balance = asyncio.run(_no_movements_balance(fx_test_dsn))
    assert balance == Decimal(0)


async def _status_filtered_listing(dsn: str):
    async with rollback_session(dsn) as session:
        repo = PostgresCardAccountRepository(session)
        customer, card_account_1, _ = await _seed_card_account(session)
        # Second card account for the SAME customer — reuse the same
        # customer/account row is not possible (one card account per row
        # here is fine, `customer_id` is the only shared FK needed).
        location = LocationORM(name=f"loc-{uuid.uuid4()}")
        session.add(location)
        await session.flush()
        branch = BranchORM(code=f"B{uuid.uuid4().hex[:8]}", name="Branch", location_id=location.id)
        session.add(branch)
        await session.flush()
        account_2 = AccountORM(
            account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
            currency="USD", customer_id=customer.id, branch_id=branch.id,
        )
        session.add(account_2)
        await session.flush()
        card_account_2 = await repo.create(
            customer_id=customer.id, paying_account_id=account_2.id, credit_limit=500
        )
        await repo.update_status(card_account_2.id, status="closed")

        active_page = await repo.list_by_customer(customer.id, limit=20, offset=0, status="active")
        closed_page = await repo.list_by_customer(customer.id, limit=20, offset=0, status="closed")
        all_page = await repo.list_by_customer(customer.id, limit=20, offset=0)
        return active_page, closed_page, all_page, card_account_1.id, card_account_2.id


def test_list_by_customer_status_filter_over_real_postgres(fx_test_dsn):
    active_page, closed_page, all_page, active_id, closed_id = asyncio.run(
        _status_filtered_listing(fx_test_dsn)
    )
    assert {a.id for a in active_page.items} == {active_id}
    assert {a.id for a in closed_page.items} == {closed_id}
    assert all_page.total == 2


async def _record_same_uow(dsn: str):
    async with rollback_session(dsn) as session:
        _, card_account, _card = await _seed_card_account(session)
        audit_repo = PostgresCardAccountAdminActionRepository(session)
        await audit_repo.record(
            card_account_id=card_account.id, action="issue", admin_id="test-admin",
            reason="onboarding", details={"credit_limit": "1000"},
        )
        from sqlalchemy import select

        from openbankapi.infra.database.schemas.models import CardAccountAdminActionORM

        result = await session.execute(
            select(CardAccountAdminActionORM).where(
                CardAccountAdminActionORM.card_account_id == card_account.id
            )
        )
        return result.scalars().all()


def test_admin_action_record_flushes_in_the_same_session(fx_test_dsn):
    rows = asyncio.run(_record_same_uow(fx_test_dsn))
    assert len(rows) == 1
    assert rows[0].action == "issue"
    assert rows[0].admin_id == "test-admin"
    assert rows[0].reason == "onboarding"
