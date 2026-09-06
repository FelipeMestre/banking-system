"""RED/GREEN for tasks C2/C4/C5(fake): fast unit-level regression net mirroring
`test_statement_aggregation_repositories.py`'s Postgres-level scenarios,
using only `FakeCardMovementRepository`/`FakeInstallmentRepository`/
`FakeCardAccountRepository`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType, Installment, InstallmentStatus
from openbankapi.tests.fakes import (
    FakeCardAccountRepository,
    FakeCardMovementRepository,
    FakeCardRepository,
    FakeInstallmentRepository,
)


async def _account_with_card(cards: FakeCardRepository, card_accounts: FakeCardAccountRepository):
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
    card_accounts.known_customers.add(customer_id)
    card_accounts.known_accounts.add(paying_account_id)
    account = await card_accounts.create(
        customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=5000
    )
    card = await cards.create(card_account_id=account.id, expiration_date=date.today() + timedelta(days=365))
    return account, card


def test_aggregation_is_account_scoped_against_fakes():
    async def scenario():
        cards = FakeCardRepository()
        card_accounts = FakeCardAccountRepository()
        movements = FakeCardMovementRepository(cards=cards)
        account_a, card_a = await _account_with_card(cards, card_accounts)
        account_b, card_b = await _account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)

        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card_a.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=Decimal("40.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card_b.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=Decimal("999.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        period_start, period_end = now.date() - timedelta(days=1), now.date() + timedelta(days=1)
        payments_a = await movements.sum_payments(account_a.id, period_start, period_end)
        payments_b = await movements.sum_payments(account_b.id, period_start, period_end)
        return payments_a, payments_b

    payments_a, payments_b = asyncio.run(scenario())
    assert payments_a == Decimal("40.00")
    assert payments_b == Decimal("999.00")


def test_single_charge_purchases_excludes_installment_plan_against_fakes():
    async def scenario():
        cards = FakeCardRepository()
        card_accounts = FakeCardAccountRepository()
        installments = FakeInstallmentRepository()
        movements = FakeCardMovementRepository(cards=cards, installments=installments)
        account, card = await _account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)

        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("850.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        plan_purchase = await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("900.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        await installments.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=plan_purchase.id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
                created_at=now,
            )
            for i in range(9)
        ])
        period_start, period_end = now.date() - timedelta(days=1), now.date() + timedelta(days=1)
        return await movements.sum_single_charge_purchases(account.id, period_start, period_end)

    total = asyncio.run(scenario())
    assert total == Decimal("850.00")


def test_get_next_due_per_plan_bills_one_installment_at_a_time_against_fake():
    async def scenario():
        installments = FakeInstallmentRepository()
        movement_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await installments.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=movement_id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
                created_at=now,
            )
            for i in range(9)
        ])
        first_round = await installments.get_next_due_per_plan(uuid.uuid4())
        first_pick = first_round[0]
        await installments.mark_billed(first_pick.id, uuid.uuid4())
        second_round = await installments.get_next_due_per_plan(uuid.uuid4())
        return first_pick, second_round[0]

    first_pick, second_pick = asyncio.run(scenario())
    assert first_pick.installment_number == 1
    assert second_pick.installment_number == 2


def test_get_total_installments_returns_max_installment_number_against_fake():
    """Derived total must reflect the FULL plan even after the first
    installment is billed (statement_id set) — matches the real
    repository's `MAX()` semantics, not just the unbilled rows."""
    async def scenario():
        installments = FakeInstallmentRepository()
        movement_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await installments.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=movement_id, installment_number=i + 1,
                amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
                created_at=now,
            )
            for i in range(9)
        ])
        first_round = await installments.get_next_due_per_plan(uuid.uuid4())
        await installments.mark_billed(first_round[0].id, uuid.uuid4())
        return await installments.get_total_installments(movement_id)

    total = asyncio.run(scenario())
    assert total == 9


def test_list_active_ids_includes_blocked_excludes_closed_against_fake():
    """A blocked card_account still has an outstanding balance and must
    still get billed — blocking only affects Phase 2's purchase check, not
    this billing phase. Only a closed account has no ongoing credit line."""
    async def scenario():
        card_accounts = FakeCardAccountRepository()
        customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
        card_accounts.known_customers.add(customer_id)
        card_accounts.known_accounts.add(paying_account_id)
        active = await card_accounts.create(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=1000
        )
        blocked = await card_accounts.create(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=1000
        )
        closed = await card_accounts.create(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=1000
        )
        await card_accounts.update_status(blocked.id, status="blocked")
        await card_accounts.update_status(closed.id, status="closed")
        active_ids = await card_accounts.list_active_ids()
        issuance_date = await card_accounts.get_issuance_date(active.id)
        return active.id, blocked.id, closed.id, active_ids, issuance_date, active.created_at

    active_id, blocked_id, closed_id, active_ids, issuance_date, created_at = asyncio.run(scenario())
    assert active_id in active_ids
    assert blocked_id in active_ids
    assert closed_id not in active_ids
    assert issuance_date == created_at.date()
