"""RED/GREEN for tasks E1-E3: `StatementService.close_statement` and
`.run_due_date_check`, exercised entirely against fakes (E1/E2/E3's explicit
scenarios, verbatim from the spec)."""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType, Installment, InstallmentStatus
from openbankapi.domain.service.statement_service import StatementService
from openbankapi.tests.fakes import (
    FakeCardAccountRepository,
    FakeCardMovementRepository,
    FakeCardRepository,
    FakeInstallmentRepository,
    FakeStatementRepository,
)

APR = Decimal("0.24")
LATE_FEE_AMOUNT = Decimal("35.00")
MIN_PAYMENT_RATE = Decimal("0.02")
DUE_OFFSET = 20


def _service(cards=None, card_accounts=None, movements=None, installments=None, statements=None):
    cards = cards or FakeCardRepository()
    card_accounts = card_accounts or FakeCardAccountRepository()
    installments = installments or FakeInstallmentRepository()
    movements = movements or FakeCardMovementRepository(cards=cards, installments=installments)
    statements = statements or FakeStatementRepository()
    service = StatementService(
        statements, movements, installments,
        credit_card_apr=APR, late_fee_amount=LATE_FEE_AMOUNT,
        minimum_payment_rate=MIN_PAYMENT_RATE, due_date_offset_days=DUE_OFFSET,
    )
    return service, cards, card_accounts, movements, installments, statements


async def _new_account_with_card(cards, card_accounts):
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
    card_accounts.known_customers.add(customer_id)
    card_accounts.known_accounts.add(paying_account_id)
    account = await card_accounts.create(
        customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=5000
    )
    card = await cards.create(card_account_id=account.id, expiration_date=date.today() + timedelta(days=365))
    return account, card


def test_close_statement_is_idempotent():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        period_end = date.today()

        first = await service.close_statement(account.id, period_end)
        second = await service.close_statement(account.id, period_end)
        return first, second, len(statements.rows)

    first, second, count = asyncio.run(scenario())
    assert count == 1
    assert first.id == second.id


def test_one_installment_billed_per_close():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
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

        first_close = await service.close_statement(account.id, now.date())
        first_purchases = first_close.purchases_total
        first_billed = [row for row in installments.rows if row.statement_id is not None]

        second_close = await service.close_statement(account.id, now.date() + timedelta(days=30))
        second_billed = [
            row for row in installments.rows
            if row.statement_id is not None and row.statement_id != first_close.id
        ]
        return first_purchases, first_billed, second_close, second_billed

    first_purchases, first_billed, second_close, second_billed = asyncio.run(scenario())
    assert first_purchases == Decimal("950.00")
    assert len(first_billed) == 1
    assert first_billed[0].installment_number == 1
    assert len(second_billed) == 1
    assert second_billed[0].installment_number == 2


def test_no_interest_on_zero_carried_balance():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        first = await service.close_statement(account.id, now.date())
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=first.total_due,
            currency="USD", created_at=datetime.now(timezone.utc), occurred_at=datetime.now(timezone.utc),
        ))
        await statements.finalize_due_date_outcome(
            first.id, paid_amount=first.total_due, paid_in_full=True, paid_by_due_date=True
        )
        second = await service.close_statement(account.id, (now.date() + timedelta(days=30)))
        return second

    second = asyncio.run(scenario())
    assert second.interest_total == Decimal("0.00")


def test_interest_matches_formula_on_partial_payment():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("1000.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        first = await service.close_statement(account.id, now.date())
        # No payment at all -> full unpaid balance carries.
        second = await service.close_statement(account.id, (now.date() + timedelta(days=30)))
        return first, second

    first, second = asyncio.run(scenario())
    expected_interest = (first.total_due * APR / 12).quantize(Decimal("0.01"))
    assert second.interest_total == expected_interest
    assert second.interest_total > Decimal("0.00")


def test_overpayment_credit_reduces_next_due():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("500.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        first = await service.close_statement(account.id, now.date())
        overpaid_by = Decimal("50.00")
        await statements.finalize_due_date_outcome(
            first.id, paid_amount=first.total_due + overpaid_by, paid_in_full=True, paid_by_due_date=True
        )

        second = await service.close_statement(account.id, (now.date() + timedelta(days=30)))
        # No new purchases this period: total_due should be reduced exactly
        # by the $50 credit relative to what it would be without it (zero).
        return second, overpaid_by

    second, overpaid_by = asyncio.run(scenario())
    assert second.credit_balance == overpaid_by
    assert second.total_due == Decimal("0.00")


def test_blocked_account_still_bills():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        plan_purchase = await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("300.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        await installments.bulk_insert([
            Installment(
                id=uuid.uuid4(), card_movement_id=plan_purchase.id, installment_number=1,
                amount=Decimal("300.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
                created_at=now,
            )
        ])
        await card_accounts.update_status(account.id, status="blocked")

        statement = await service.close_statement(account.id, now.date())
        return statement

    statement = asyncio.run(scenario())
    assert statement is not None
    assert statement.purchases_total == Decimal("300.00")


def test_thresholds_disagree_simultaneously():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("1000.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        statement = await service.close_statement(account.id, now.date())
        payment = statement.minimum_payment  # exactly the minimum, less than total_due
        assert payment < statement.total_due
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=payment,
            currency="USD", created_at=now, occurred_at=statement.due_date and datetime.combine(statement.due_date, datetime.min.time(), tzinfo=timezone.utc),
        ))
        await service.run_due_date_check(statement.due_date)
        finalized = await statements.get_latest(account.id)
        late_fee_movements = [m for m in movements.rows if m.movement_type == CardMovementType.LATE_FEE]
        return finalized, late_fee_movements

    finalized, late_fee_movements = asyncio.run(scenario())
    assert finalized.paid_by_due_date is True
    assert finalized.paid_in_full is False
    assert late_fee_movements == []


def test_late_fee_capped_at_minimum_payment():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        service._late_fee_amount = Decimal("8.00")  # tiny minimum, larger configured late fee
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("100.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        statement = await service.close_statement(account.id, now.date())
        # Force a deliberately tiny minimum_payment for this test's assertion,
        # simulating a plan where the cap ($8 configured) exceeds it.
        object.__setattr__(statement, "minimum_payment", Decimal("5.00"))
        statements.rows[statement.id] = statement

        await service.run_due_date_check(statement.due_date)
        late_fee_movements = [m for m in movements.rows if m.movement_type == CardMovementType.LATE_FEE]
        return late_fee_movements

    late_fee_movements = asyncio.run(scenario())
    assert len(late_fee_movements) == 1
    assert late_fee_movements[0].amount == Decimal("5.00")


def test_run_due_date_check_finalizes_once_no_double_late_fee():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        now = datetime.now(timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("100.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        statement = await service.close_statement(account.id, now.date())

        await service.run_due_date_check(statement.due_date)
        await service.run_due_date_check(statement.due_date)  # same day, called twice

        late_fee_movements = [m for m in movements.rows if m.movement_type == CardMovementType.LATE_FEE]
        return late_fee_movements

    late_fee_movements = asyncio.run(scenario())
    assert len(late_fee_movements) == 1
