"""RED/GREEN for tasks G1-G4: `next_close_date_after`, `check_and_close_if_due`
(downtime-safe targeting — spec §9 step 7, this phase's single most
safety-critical scenario), `run_once_with` (duplicate-tick safety), and the
composition-root isolation guarantee (`openbankapi.main` never imported).
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.batch.run_once import check_and_close_if_due, next_close_date_after, run_once_with
from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.domain.service.statement_service import StatementService
from openbankapi.tests.fakes import (
    FakeCardAccountRepository,
    FakeCardMovementRepository,
    FakeCardRepository,
    FakeInstallmentRepository,
    FakeStatementRepository,
)

CLOSE_DAY = 20
APR = Decimal("0.24")
LATE_FEE_AMOUNT = Decimal("35.00")
MIN_PAYMENT_RATE = Decimal("0.02")
DUE_OFFSET = 20


# --- G1: next_close_date_after -------------------------------------------

def test_standard_case_today_before_close_day_returns_this_month():
    result = next_close_date_after(date(2026, 9, 5), CLOSE_DAY)
    assert result == date(2026, 9, 20)


def test_boundary_case_today_equals_close_day_returns_same_day():
    result = next_close_date_after(date(2026, 9, 20), CLOSE_DAY)
    assert result == date(2026, 9, 20)


def test_rollover_case_today_after_close_day_returns_next_month():
    result = next_close_date_after(date(2026, 9, 25), CLOSE_DAY)
    assert result == date(2026, 10, 20)


# --- setup helpers ----------------------------------------------------------

def _wiring():
    cards = FakeCardRepository()
    card_accounts = FakeCardAccountRepository()
    installments = FakeInstallmentRepository()
    movements = FakeCardMovementRepository(cards=cards, installments=installments)
    statements = FakeStatementRepository()
    service = StatementService(
        statements, movements, installments, cards,
        credit_card_apr=APR, late_fee_amount=LATE_FEE_AMOUNT,
        minimum_payment_rate=MIN_PAYMENT_RATE, due_date_offset_days=DUE_OFFSET,
    )
    return service, statements, card_accounts, cards, movements, installments


async def _new_account_with_card(cards, card_accounts, *, issued_on: date):
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
    card_accounts.known_customers.add(customer_id)
    card_accounts.known_accounts.add(paying_account_id)
    account = await card_accounts.create(
        customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=5000
    )
    # Backdate `created_at` (issuance date) to the requested date directly on
    # the fake's stored row — the fake's `create()` always stamps "now".
    import dataclasses
    backdated = dataclasses.replace(account, created_at=datetime.combine(issued_on, datetime.min.time(), tzinfo=timezone.utc))
    card_accounts.rows[account.id] = backdated
    card = await cards.create(card_account_id=account.id, expiration_date=date.today() + timedelta(days=365 * 4))
    return backdated, card


# --- G2: downtime-safe targeting (spec §9 step 7) --------------------------

def test_missed_tick_still_records_intended_close_date_not_the_late_catch_up_day():
    async def scenario():
        service, statements, card_accounts, cards, movements, installments = _wiring()
        account, card = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 6, 1))

        # Account already had a normal close in August — this is what the
        # worker's "next" target should advance from.
        await statements.create(
            account.id, date(2026, 7, 20), date(2026, 8, 20), date(2026, 9, 9),
            purchases_total=Decimal("100.00"), interest_total=Decimal("0"),
            total_due=Decimal("100.00"), credit_balance=Decimal("0"),
            late_fees_total=Decimal("0"), minimum_payment=Decimal("10.00"),
        )

        # Worker "down" until day 25 — first invocation happens on the 25th,
        # five days after the missed CLOSE_DAY=20 September tick.
        simulated_today = date(2026, 9, 25)
        statement = await check_and_close_if_due(
            service, statements, card_accounts, account.id, simulated_today, CLOSE_DAY
        )
        return statement

    statement = asyncio.run(scenario())
    assert statement is not None
    assert statement.period_end == date(2026, 9, 20)
    assert statement.period_end != date(2026, 9, 25)


def test_multi_period_catch_up_creates_one_distinct_statement_per_missed_period():
    """Correction for sdd-verify WARNING (MULTI-PERIOD-CATCHUP-UNTESTED): the
    existing downtime test only ever simulates a SINGLE missed period, so the
    loop in `check_and_close_if_due` only ever executes once there. This
    proves the loop itself, in ONE invocation, catches up 3+ distinct missed
    periods with no duplicates and no skipped periods."""
    async def scenario():
        service, statements, card_accounts, cards, movements, installments = _wiring()
        account, card = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 6, 1))

        # Worker down since issuance — first-ever run happens on 2026-12-01,
        # five full CLOSE_DAY=20 ticks behind (Jun, Jul, Aug, Sep, Oct, Nov).
        simulated_today = date(2026, 12, 1)
        statement = await check_and_close_if_due(
            service, statements, card_accounts, account.id, simulated_today, CLOSE_DAY
        )
        account_statements = [row for row in statements.rows.values() if row.card_account_id == account.id]
        return statement, account_statements

    last_statement, account_statements = asyncio.run(scenario())

    period_ends = sorted(row.period_end for row in account_statements)
    expected_period_ends = [
        date(2026, 6, 20), date(2026, 7, 20), date(2026, 8, 20),
        date(2026, 9, 20), date(2026, 10, 20), date(2026, 11, 20),
    ]
    assert period_ends == expected_period_ends, "expected exactly one statement per missed period, none skipped"
    assert len(period_ends) == len(set(period_ends)), "no duplicate period_end statements"
    assert last_statement is not None
    assert last_statement.period_end == date(2026, 11, 20), "loop must return the LAST period closed"


def test_not_yet_due_skips_close():
    async def scenario():
        service, statements, card_accounts, cards, movements, installments = _wiring()
        account, card = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 9, 1))
        # Today is before CLOSE_DAY this month — nothing should close yet.
        result = await check_and_close_if_due(
            service, statements, card_accounts, account.id, date(2026, 9, 5), CLOSE_DAY
        )
        return result, len(statements.rows)

    result, count = asyncio.run(scenario())
    assert result is None
    assert count == 0


# --- G3: duplicate-tick safety ----------------------------------------------

def test_hourly_tick_does_not_double_close():
    async def scenario():
        service, statements, card_accounts, cards, movements, installments = _wiring()
        # Issued just before the current period's close day: exactly ONE
        # period (this month's) is due by `today` — isolates the duplicate-
        # tick assertion from legitimate multi-period catch-up.
        account, card = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 9, 1))
        today = date(2026, 9, 20)

        await run_once_with(service, statements, card_accounts, today, CLOSE_DAY)
        await run_once_with(service, statements, card_accounts, today, CLOSE_DAY)  # same hour/day, twice

        return [row for row in statements.rows.values() if row.card_account_id == account.id]

    account_statements = asyncio.run(scenario())
    assert len(account_statements) == 1


# --- Correction: blocked accounts must reach the real batch pipeline -------
# (sdd-verify CRITICAL: BLOCKED-ACCOUNT-NEVER-BATCHED). `list_active_ids()`
# previously filtered to `status == ACTIVE`, so `run_once_with` — the real
# orchestration entry point the cron job calls — never visited a BLOCKED
# account. The unit-level `test_blocked_account_still_bills` in
# `test_statement_service.py` called `close_statement` directly, bypassing
# `list_active_ids()`/`run_once_with` entirely, so it gave false confidence.
# This test goes through the REAL selection path.

def test_run_once_with_bills_active_and_blocked_but_not_closed_accounts():
    async def scenario():
        service, statements, card_accounts, cards, movements, installments = _wiring()
        today = date(2026, 9, 20)

        active, _ = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 9, 1))
        blocked, _ = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 9, 1))
        closed, _ = await _new_account_with_card(cards, card_accounts, issued_on=date(2026, 9, 1))
        await card_accounts.update_status(blocked.id, status="blocked")
        await card_accounts.update_status(closed.id, status="closed")

        await run_once_with(service, statements, card_accounts, today, CLOSE_DAY)

        return statements.rows

    rows = asyncio.run(scenario())
    account_ids_billed = {row.card_account_id for row in rows.values()}
    assert len(account_ids_billed) == 2, "expected exactly active + blocked accounts to be billed"
    billed_active = [r for r in rows.values() if r.period_end == date(2026, 9, 20)]
    assert len(billed_active) == 2


# --- G4: composition root isolation -----------------------------------------

def test_run_once_module_never_imports_openbankapi_main():
    """A fresh interpreter that imports only `openbankapi.batch.run_once`
    must never pull in `openbankapi.main`/`openbankapi.app` — the whole
    point of the composition-root isolation decision. Run in a subprocess:
    this repo's own test suite already imports `openbankapi.app` via
    `conftest.py`, so checking `sys.modules` in-process would prove nothing.
    """
    import subprocess

    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; import openbankapi.batch.run_once; "
            "assert 'openbankapi.main' not in sys.modules; "
            "assert 'openbankapi.app' not in sys.modules; "
            "print('OK')",
        ],
        capture_output=True, text=True, cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
