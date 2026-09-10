"""RED/GREEN for `credit-cards-frontend-page` Group B: renewal-continuity.

Proves `PostgresCardMovementRepository.get_by_card_account_id` spans card
renewals — a movement posted against a since-replaced card must still show
up when querying by the enduring `card_account_id`, not just the currently
active card. Mirrors `test_postgres_card_movement_and_installment_repository.py`'s
harness (real Postgres via `fx_test_dsn`).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.infra.database.repositories.postgres_card_account_repository import (
    PostgresCardAccountRepository,
)
from openbankapi.infra.database.repositories.postgres_card_movement_repository import (
    PostgresCardMovementRepository,
)
from openbankapi.infra.database.repositories.postgres_card_repository import PostgresCardRepository
from openbankapi.infra.database.schemas.models import AccountORM, CustomerORM
from openbankapi.tests.db_fixtures import rollback_session


async def _seed_card_account(session):
    customer = CustomerORM(
        identification_number=f"id-{uuid.uuid4().hex[:16]}",
        first_name="Grace",
        last_name="Hopper",
        date_of_birth=datetime(1985, 1, 1).date(),
    )
    session.add(customer)
    await session.flush()
    account = AccountORM(
        account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
        currency="USD",
        customer_id=customer.id,
    )
    session.add(account)
    await session.flush()
    return await PostgresCardAccountRepository(session).create(
        customer_id=customer.id, paying_account_id=account.id, credit_limit=1000
    )


def _purchase(card_id, amount: str, now: datetime) -> CardMovement:
    return CardMovement(
        id=uuid.uuid4(),
        card_id=card_id,
        request_id=uuid.uuid4(),
        movement_type=CardMovementType.PURCHASE,
        amount=Decimal(amount),
        currency="USD",
        created_at=now,
    )


async def _renewal_continuity(dsn: str):
    async with rollback_session(dsn) as session:
        card_account = await _seed_card_account(session)
        card_repo = PostgresCardRepository(session)
        movement_repo = PostgresCardMovementRepository(session)
        now = datetime.now(timezone.utc)

        original_card = await card_repo.create(
            card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
        )
        movement_a = await movement_repo.insert(_purchase(original_card.id, "40.00", now))

        # Renew: original card -> replaced, a brand new card issued under the
        # SAME card_account_id (the enduring "one card" entity in the UI).
        await card_repo.mark_replaced(original_card.id)
        renewed_card = await card_repo.create(
            card_account_id=card_account.id, expiration_date=date.today() + timedelta(days=365 * 4)
        )
        movement_b = await movement_repo.insert(
            _purchase(renewed_card.id, "15.00", now + timedelta(seconds=1))
        )

        history = await movement_repo.get_by_card_account_id(card_account.id)
        return movement_a, movement_b, history


def test_movements_span_renewal_by_card_account_id(fx_test_dsn):
    movement_a, movement_b, history = asyncio.run(_renewal_continuity(fx_test_dsn))

    # Both the pre-renewal (movement_a) and post-renewal (movement_b) purchases
    # appear — the whole point of scoping by card_account_id instead of the
    # currently-active card_id alone. (`created_at` is a server-assigned
    # transaction timestamp here, shared by both inserts in this single
    # transaction, so exact newest-first order between these two ties and is
    # not asserted — real ordering is already covered by A2's dedicated test.)
    history_ids = {row.id for row in history}
    assert history_ids == {movement_a.id, movement_b.id}
    total_used = sum(row.amount for row in history)
    assert total_used == Decimal("55.00")
