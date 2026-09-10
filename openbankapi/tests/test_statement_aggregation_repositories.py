"""RED for tasks C1/C3/C5: account-scoped aggregation methods against real
Postgres. Mirrors `test_postgres_card_movement_and_installment_repository.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType, Installment, InstallmentStatus
from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_card_movement_repository import (
    PostgresCardMovementRepository,
)
from openbankapi.infra.database.repositories.postgres_card_repository import PostgresCardRepository
from openbankapi.infra.database.repositories.postgres_installment_repository import (
    PostgresInstallmentRepository,
)
from openbankapi.infra.database.repositories.postgres_statement_repository import (
    PostgresStatementRepository,
)
from openbankapi.infra.database.schemas.models import AccountORM, CustomerORM
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card_account(session, *, status: str = "active"):
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
    card_account = await PostgresCardAccountRepository(session).create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=5000
    )
    if status != "active":
        await PostgresCardAccountRepository(session).update_status(card_account.id, status=status)
    card = await PostgresCardRepository(session).create(
        card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
    )
    return card_account, card


async def _insert_purchase(session, card, amount: Decimal, occurred_at: datetime):
    return await PostgresCardMovementRepository(session).insert(
        CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=amount, currency="USD",
            created_at=occurred_at, occurred_at=occurred_at,
        )
    )


async def _exercise_aggregation_is_account_scoped(dsn: str):
    async with rollback_session(dsn) as session:
        account_a, card_a = await _seed_card_account(session)
        account_b, card_b = await _seed_card_account(session)
        now = datetime.now(timezone.utc)

        await _insert_purchase(session, card_a, Decimal("100.00"), now)
        await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card_a.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.PAYMENT, amount=Decimal("40.00"),
                currency="USD", created_at=now, occurred_at=now,
            )
        )
        await _insert_purchase(session, card_b, Decimal("999.00"), now)

        movement_repo = PostgresCardMovementRepository(session)
        period_start = now.date() - timedelta(days=30)
        period_end = now.date() + timedelta(days=1)
        payments_a = await movement_repo.sum_payments(account_a.id, period_start, period_end)
        purchases_a = await movement_repo.sum_single_charge_purchases(account_a.id, period_start, period_end)
        purchases_b = await movement_repo.sum_single_charge_purchases(account_b.id, period_start, period_end)
        return payments_a, purchases_a, purchases_b


def test_aggregation_is_account_scoped(fx_test_dsn):
    payments_a, purchases_a, purchases_b = asyncio.run(
        _exercise_aggregation_is_account_scoped(fx_test_dsn)
    )
    assert payments_a == Decimal("40.00")
    assert purchases_a == Decimal("100.00")
    assert purchases_b == Decimal("999.00")


async def _exercise_single_charge_excludes_installment_plans_and_late_fee(dsn: str):
    async with rollback_session(dsn) as session:
        account, card = await _seed_card_account(session)
        now = datetime.now(timezone.utc)

        single_charge = await _insert_purchase(session, card, Decimal("850.00"), now)
        plan_purchase = await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.PURCHASE, amount=Decimal("900.00"),
                currency="USD", created_at=now, occurred_at=now,
            )
        )
        await PostgresInstallmentRepository(session).bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=plan_purchase.id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today() + timedelta(days=30 * (i + 1)),
                status=InstallmentStatus.PENDING, created_at=now,
            )
            for i in range(9)
        ])
        await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.LATE_FEE,
                amount=Decimal("25.00"), currency="USD", created_at=now, occurred_at=now,
            )
        )

        movement_repo = PostgresCardMovementRepository(session)
        period_start = now.date() - timedelta(days=1)
        period_end = now.date() + timedelta(days=1)
        single_charge_total = await movement_repo.sum_single_charge_purchases(account.id, period_start, period_end)
        late_fee_total = await movement_repo.sum_by_type(account.id, "late_fee", period_start, period_end)
        return single_charge_total, late_fee_total


def test_single_charge_purchases_excludes_installment_plans(fx_test_dsn):
    single_charge_total, late_fee_total = asyncio.run(
        _exercise_single_charge_excludes_installment_plans_and_late_fee(fx_test_dsn)
    )
    assert single_charge_total == Decimal("850.00")
    assert late_fee_total == Decimal("25.00")


async def _exercise_next_due_per_plan_bills_one_at_a_time(dsn: str):
    async with rollback_session(dsn) as session:
        account, card = await _seed_card_account(session)
        now = datetime.now(timezone.utc)
        movement = await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.PURCHASE, amount=Decimal("900.00"),
                currency="USD", created_at=now, occurred_at=now,
            )
        )
        installment_repo = PostgresInstallmentRepository(session)
        await installment_repo.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=movement.id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today() + timedelta(days=30 * (i + 1)),
                status=InstallmentStatus.PENDING, created_at=now,
            )
            for i in range(9)
        ])

        first_round = await installment_repo.get_next_due_per_plan(account.id)
        first_pick = first_round[0]
        assert first_pick.installment_number == 1

        fake_statement_id = uuid.uuid4()
        # statements table needs a real row for the FK — use a minimal insert
        from openbankapi.infra.database.repositories.postgres_statement_repository import (
            PostgresStatementRepository,
        )
        statement = await PostgresStatementRepository(session).create(
            account.id, date.today(), date.today(), date.today() + timedelta(days=20),
            purchases_total=Decimal("900.00"), interest_total=Decimal("0"),
            total_due=Decimal("900.00"), credit_balance=Decimal("0"),
            late_fees_total=Decimal("0"), minimum_payment=Decimal("25.00"),
        )
        await installment_repo.mark_billed(first_pick.id, statement.id)

        second_round = await installment_repo.get_next_due_per_plan(account.id)
        second_pick = second_round[0]
        return first_pick, second_pick


def test_second_close_bills_the_next_installment(fx_test_dsn):
    first_pick, second_pick = asyncio.run(_exercise_next_due_per_plan_bills_one_at_a_time(fx_test_dsn))
    assert first_pick.installment_number == 1
    assert second_pick.installment_number == 2


# --- Correction: derived total_installments count (sdd-verify CRITICAL:
# DERIVED-INSTALLMENT-COUNT-UNIMPLEMENTED). The spec requires the plan's
# total installment count to be computable as MAX(installment_number) per
# card_movement_id at read time — never stored as a column. Regardless of
# how many installments have already been billed (statement_id set), the
# total must still reflect the full plan size.

async def _exercise_get_total_installments(dsn: str):
    async with rollback_session(dsn) as session:
        account, card = await _seed_card_account(session)
        now = datetime.now(timezone.utc)
        movement = await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.PURCHASE, amount=Decimal("900.00"),
                currency="USD", created_at=now, occurred_at=now,
            )
        )
        installment_repo = PostgresInstallmentRepository(session)
        await installment_repo.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=movement.id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today() + timedelta(days=30 * (i + 1)),
                status=InstallmentStatus.PENDING, created_at=now,
            )
            for i in range(9)
        ])
        # Bill the first installment before reading the total — the total
        # must still be 9, not 8, since it is derived from the FULL plan,
        # not only the still-unbilled rows.
        first_round = await installment_repo.get_next_due_per_plan(account.id)
        fake_statement_id = uuid.uuid4()
        from openbankapi.infra.database.repositories.postgres_statement_repository import (
            PostgresStatementRepository,
        )
        statement = await PostgresStatementRepository(session).create(
            account.id, date.today(), date.today(), date.today() + timedelta(days=20),
            purchases_total=Decimal("900.00"), interest_total=Decimal("0"),
            total_due=Decimal("900.00"), credit_balance=Decimal("0"),
            late_fees_total=Decimal("0"), minimum_payment=Decimal("25.00"),
        )
        await installment_repo.mark_billed(first_round[0].id, statement.id)

        return await installment_repo.get_total_installments(movement.id)


def test_get_total_installments_returns_max_installment_number_regardless_of_billed(fx_test_dsn):
    total = asyncio.run(_exercise_get_total_installments(fx_test_dsn))
    assert total == 9


async def _exercise_list_active_ids(dsn: str):
    async with rollback_session(dsn) as session:
        active_account, _ = await _seed_card_account(session, status="active")
        blocked_account, _ = await _seed_card_account(session, status="blocked")
        closed_account, _ = await _seed_card_account(session, status="closed")
        repo = PostgresCardAccountRepository(session)
        active_ids = await repo.list_active_ids()
        issuance_date = await repo.get_issuance_date(active_account.id)
        return (
            active_account.id, blocked_account.id, closed_account.id,
            active_ids, issuance_date, active_account.created_at,
        )


def test_list_active_ids_includes_blocked_excludes_closed_and_issuance_date_matches_created_at(fx_test_dsn):
    """A blocked card_account still has an outstanding balance and must
    still get billed — blocking only affects Phase 2's purchase check, not
    this billing phase. Only a closed account has no ongoing credit line."""
    active_id, blocked_id, closed_id, active_ids, issuance_date, created_at = asyncio.run(
        _exercise_list_active_ids(fx_test_dsn)
    )
    assert active_id in active_ids
    assert blocked_id in active_ids
    assert closed_id not in active_ids
    assert issuance_date == created_at.date()


async def _exercise_get_by_statement_id_and_sum_unbilled(dsn: str):
    async with rollback_session(dsn) as session:
        account, card = await _seed_card_account(session)
        now = datetime.now(timezone.utc)
        movement = await PostgresCardMovementRepository(session).insert(
            CardMovement(
                id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
                movement_type=CardMovementType.PURCHASE, amount=Decimal("300.00"),
                currency="USD", created_at=now, occurred_at=now,
            )
        )
        installment_repo = PostgresInstallmentRepository(session)
        await installment_repo.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=movement.id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today() + timedelta(days=30 * (i + 1)),
                status=InstallmentStatus.PENDING, created_at=now,
            )
            for i in range(3)
        ])

        unbilled_before = await installment_repo.sum_unbilled(account.id)
        first_due = (await installment_repo.get_next_due_per_plan(account.id))[0]

        statement = await PostgresStatementRepository(session).create(
            account.id, date.today(), date.today(), date.today() + timedelta(days=20),
            purchases_total=Decimal("100.00"), interest_total=Decimal("0"),
            total_due=Decimal("100.00"), credit_balance=Decimal("0"),
            late_fees_total=Decimal("0"), minimum_payment=Decimal("10.00"),
        )
        await installment_repo.mark_billed(first_due.id, statement.id)

        unbilled_after = await installment_repo.sum_unbilled(account.id)
        billed_for_statement = await installment_repo.get_by_statement_id(statement.id)
        return unbilled_before, unbilled_after, billed_for_statement


def test_get_by_statement_id_and_sum_unbilled_against_postgres(fx_test_dsn):
    unbilled_before, unbilled_after, billed_for_statement = asyncio.run(
        _exercise_get_by_statement_id_and_sum_unbilled(fx_test_dsn)
    )

    assert unbilled_before == Decimal("300.00")
    assert unbilled_after == Decimal("200.00")
    assert [row.installment_number for row in billed_for_statement] == [1]
