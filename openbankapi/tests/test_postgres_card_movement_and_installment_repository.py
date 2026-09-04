"""RED for Credit Cards Phase 2 (task 1.8): `PostgresCardMovementRepository`
and `PostgresInstallmentRepository` — insert idempotency + bulk_insert linkage.
Real Postgres via `fx_test_dsn`, mirrors `test_card_repository.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import (
    CardMovement,
    CardMovementType,
    Installment,
    InstallmentStatus,
)
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
    return await PostgresCardRepository(session).create(
        card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
    )


async def _insert_movement_and_installments(dsn: str):
    async with rollback_session(dsn) as session:
        card = await _seed_card(session)
        movement_repo = PostgresCardMovementRepository(session)
        installment_repo = PostgresInstallmentRepository(session)
        request_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        movement = CardMovement(
            id=uuid.uuid4(),
            card_id=card.id,
            request_id=request_id,
            movement_type=CardMovementType.PURCHASE,
            amount=Decimal("100.00"),
            currency="USD",
            created_at=now,
        )
        inserted = await movement_repo.insert(movement)
        # Idempotent redelivery: same (request_id, movement_type) is a no-op.
        redelivered = await movement_repo.insert(movement)

        installments = [
            Installment(
                id=uuid.uuid4(),
                card_movement_id=inserted.id,
                installment_number=i + 1,
                amount=amount,
                due_date=date.today() + timedelta(days=30 * (i + 1)),
                status=InstallmentStatus.PENDING,
                created_at=now,
            )
            for i, amount in enumerate([Decimal("33.34"), Decimal("33.33"), Decimal("33.33")])
        ]
        await installment_repo.bulk_insert(installments)

        by_card = await movement_repo.get_by_card_id(card.id)
        by_movement = await installment_repo.get_by_movement_id(inserted.id)
        return inserted, redelivered, by_card, by_movement


def test_insert_is_idempotent_and_bulk_insert_links_installments(fx_test_dsn):
    inserted, redelivered, by_card, by_movement = asyncio.run(
        _insert_movement_and_installments(fx_test_dsn)
    )
    assert inserted.movement_type == CardMovementType.PURCHASE
    assert redelivered.id == inserted.id
    assert len(by_card) == 1
    assert len(by_movement) == 3
    assert sum(i.amount for i in by_movement) == Decimal("100.00")
