"""RED/GREEN for `CurrentCycleProjectionService.project` — the 4 spec
scenarios from `sdd/credit-card-current-cycle/spec`, plus the freshness
(never-persisted, always-recomputed) requirement. Exercised entirely against
fakes, no DB."""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.domain.service.current_cycle_projection_service import (
    CurrentCycleProjectionService,
)
from openbankapi.tests.fakes import (
    FakeCardAccountRepository,
    FakeCardMovementRepository,
    FakeCardRepository,
    FakeInstallmentRepository,
    FakeStatementRepository,
)

APR = Decimal("0.24")
CLOSE_DAY = 20


def _service(cards=None, card_accounts=None, movements=None, installments=None, statements=None):
    cards = cards or FakeCardRepository()
    card_accounts = card_accounts or FakeCardAccountRepository()
    installments = installments or FakeInstallmentRepository()
    movements = movements or FakeCardMovementRepository(cards=cards, installments=installments)
    statements = statements or FakeStatementRepository()
    service = CurrentCycleProjectionService(
        statements, movements, installments, card_accounts,
        credit_card_apr=APR, close_day=CLOSE_DAY,
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


def test_due_date_not_yet_passed_overdue_absent_even_if_unpaid():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        previous = await statements.create(
            account.id, date(2026, 7, 21), date(2026, 8, 20), date(2026, 9, 9),
            purchases_total=Decimal("500.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("500.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("50.00"),
        )
        today = date(2026, 9, 5)  # before previous.due_date (2026-09-09), still unpaid
        return await service.project(account.id, today)

    projection = asyncio.run(scenario())
    assert projection.overdue_from_previous_cycle is None
    assert projection.interest_on_overdue is None
    assert projection.total_to_pay == projection.new_purchases_this_cycle


def test_due_date_passed_not_yet_finalized_uses_live_sum_payments():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        previous = await statements.create(
            account.id, date(2026, 7, 21), date(2026, 8, 20), date(2026, 9, 9),
            purchases_total=Decimal("1000.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("1000.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("100.00"),
        )
        # Statement still `closed` (not finalized). Some payment made
        # AFTER close, within [period_start, today], but not tracked on the
        # statement's frozen `paid_amount` field (still 0 on the fake).
        now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=Decimal("400.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        assert previous.status.value == "closed"
        assert previous.paid_amount == Decimal("0")
        today = date(2026, 9, 15)  # after previous.due_date
        return await service.project(account.id, today)

    projection = asyncio.run(scenario())
    # Live-computed: 1000 - 400 = 600, NOT 1000 - 0 = 1000 (frozen field).
    assert projection.overdue_from_previous_cycle == Decimal("600.00")
    assert projection.interest_on_overdue == (Decimal("600.00") * APR / 12).quantize(Decimal("0.01"))
    assert projection.total_to_pay == (
        projection.new_purchases_this_cycle
        + projection.overdue_from_previous_cycle
        + projection.interest_on_overdue
    )


def test_previous_statement_finalized_overdue_trusts_frozen_fields():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        previous = await statements.create(
            account.id, date(2026, 7, 21), date(2026, 8, 20), date(2026, 9, 9),
            purchases_total=Decimal("1000.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("1000.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("100.00"),
        )
        # Finalized by run_due_date_check: status -> overdue, paid_amount frozen at 300.
        await statements.finalize_due_date_outcome(
            previous.id, paid_amount=Decimal("300.00"), paid_in_full=False, paid_by_due_date=False
        )
        # A payment made AFTER finalization must NOT be picked up live —
        # the frozen `paid_amount` field is authoritative once finalized.
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PAYMENT, amount=Decimal("999.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        today = date(2026, 9, 20)
        return await service.project(account.id, today)

    projection = asyncio.run(scenario())
    # Frozen: 1000 - 300 = 700, NOT the live-payment-inflated 1.
    assert projection.overdue_from_previous_cycle == Decimal("700.00")
    assert projection.interest_on_overdue == (Decimal("700.00") * APR / 12).quantize(Decimal("0.01"))


def test_previous_statement_fully_paid_no_overdue_line():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        previous = await statements.create(
            account.id, date(2026, 7, 21), date(2026, 8, 20), date(2026, 9, 9),
            purchases_total=Decimal("500.00"), interest_total=Decimal("0.00"),
            total_due=Decimal("500.00"), credit_balance=Decimal("0.00"),
            late_fees_total=Decimal("0.00"), minimum_payment=Decimal("50.00"),
        )
        await statements.finalize_due_date_outcome(
            previous.id, paid_amount=Decimal("500.00"), paid_in_full=True, paid_by_due_date=True
        )
        today = date(2026, 9, 20)
        return await service.project(account.id, today)

    projection = asyncio.run(scenario())
    assert projection.overdue_from_previous_cycle is None
    assert projection.interest_on_overdue is None


def test_idempotent_repeated_calls_with_no_intervening_change():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        today = date(2026, 9, 5)
        first = await service.project(account.id, today)
        second = await service.project(account.id, today)
        return first, second

    first, second = asyncio.run(scenario())
    assert first == second


def test_new_purchase_reflected_immediately_with_no_cache():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        today = account.created_at.date() + timedelta(days=1)
        before = await service.project(account.id, today)
        now = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        await movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("75.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        after = await service.project(account.id, today)
        return before, after

    before, after = asyncio.run(scenario())
    assert after.new_purchases_this_cycle == before.new_purchases_this_cycle + Decimal("75.00")
    assert after.total_to_pay == before.total_to_pay + Decimal("75.00")


def test_no_previous_statement_uses_issuance_date_as_period_start():
    async def scenario():
        service, cards, card_accounts, movements, installments, statements = _service()
        account, card = await _new_account_with_card(cards, card_accounts)
        today = date(2026, 9, 5)
        return account, await service.project(account.id, today)

    account, projection = asyncio.run(scenario())
    assert projection.period_start == account.created_at.date()
    assert projection.overdue_from_previous_cycle is None
    assert projection.interest_on_overdue is None
