"""RED for Credit Cards Phase 3 — full pipeline integration (task 16), real
Postgres, no DB mocking (per this repo's own documented anti-pattern list).

`account-service` and `card-service` are separate Flink jobs, not processes
this test suite can start — but both jobs' decision logic (`domain.decide`)
is pure Python with zero PyFlink imports (each module's own docstring says
so), exactly the precedent `test_transfer_conversion_e2e.py` already
established for the transfer pipeline. This test drives the real payment
pipeline end to end by composing the real pieces directly:

    router logic (real repos, real `convert()`)
      -> account-service `domain.decide()` (real, imported from
         `account-service/domain.py`)
      -> card-service `domain.decide()` (real, imported from
         `card-service/domain.py`)
      -> `CardMovementConsumer._apply()` (real, backed by real Postgres)
      -> `TransactionConsumer._apply()` (real, backed by real Postgres)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import importlib.util
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import select

from openbankapi.config import Settings
from openbankapi.domain.service.conversion_service import convert
from openbankapi.infra.database.repositories.postgres_applied_rate_repository import (
    PostgresAppliedRateRepository,
)
from openbankapi.infra.database.repositories.postgres_card_movement_repository import (
    PostgresCardMovementRepository,
)
from openbankapi.infra.database.repositories.postgres_installment_repository import (
    PostgresInstallmentRepository,
)
from openbankapi.infra.database.repositories.postgres_transaction_repository import (
    PostgresTransactionRepository,
)
from openbankapi.infra.database.schemas.models import (
    AccountORM,
    BranchORM,
    CardAccountORM,
    CardMovementORM,
    CardORM,
    CustomerORM,
    LocationORM,
    TransactionORM,
)
from openbankapi.infra.kafka.consumers.card_movement_consumer import CardMovementConsumer
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer
from openbankapi.tests.db_fixtures import rollback_session

_ACCOUNT_SERVICE_DIR = Path(__file__).resolve().parents[2] / "account-service"
if str(_ACCOUNT_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_ACCOUNT_SERVICE_DIR))

from domain import LedgerState  # noqa: E402
from domain import decide as account_decide  # noqa: E402

_CARD_SERVICE_DOMAIN_PATH = Path(__file__).resolve().parents[2] / "card-service" / "domain.py"
_card_spec = importlib.util.spec_from_file_location("card_domain_integration", _CARD_SERVICE_DOMAIN_PATH)
card_domain = importlib.util.module_from_spec(_card_spec)
sys.modules["card_domain_integration"] = card_domain
_card_spec.loader.exec_module(card_domain)

TS = "2026-09-04T12:00:00Z"
RATES = {"EUR": 0.8613, "GBP": 0.74}


async def _seed_reference_data(session):
    location = LocationORM(name="Test HQ", active=True)
    session.add(location)
    await session.flush()
    branch = BranchORM(code=f"B{uuid.uuid4().hex[:6]}", name="Test Branch", location_id=location.id, active=True)
    session.add(branch)
    await session.flush()
    customer = CustomerORM(
        identification_number=str(uuid.uuid4().int)[:15],
        first_name="Test", last_name="Customer", date_of_birth=dt.date(1990, 1, 1),
    )
    session.add(customer)
    await session.flush()
    return customer, branch


async def _seed_paying_account(session, customer, branch, *, currency: str, balance: int) -> AccountORM:
    account = AccountORM(
        account_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
        currency=currency, customer_id=customer.id, branch_id=branch.id,
        balance=balance, status="active",
    )
    session.add(account)
    await session.flush()
    return account


async def _seed_card_account_with_active_card(session, customer, paying_account) -> tuple:
    card_account = CardAccountORM(
        customer_id=customer.id, paying_account_id=paying_account.id, credit_limit=Decimal("500000.00"),
    )
    session.add(card_account)
    await session.flush()

    card = CardORM(
        card_account_id=card_account.id,
        card_number=str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0"),
        expiration_date=dt.date(2030, 1, 1),
    )
    session.add(card)
    await session.flush()
    return card_account, card


async def _run_pipeline(
    session, *, paying_currency: str, amount: int, balance: int, used_credit: int = 50000,
):
    """Router logic (manual, mirrors `card_account_router.request_payment`)
    -> account-service decide() -> card-service decide() -> real consumers.
    """
    customer, branch = await _seed_reference_data(session)
    paying_account = await _seed_paying_account(
        session, customer, branch, currency=paying_currency, balance=balance
    )
    card_account, card = await _seed_card_account_with_active_card(session, customer, paying_account)

    amount_usd = amount
    conversion = None
    if paying_currency != "USD":
        quote = convert(amount, paying_currency, "USD", "debit", RATES)
        amount_usd = quote["final_amount"]
        conversion = quote["applied_rate"]

    request_id = str(uuid.uuid4())
    wire = {
        "type": "payment_requested",
        "request_id": request_id,
        "destination_account": card.card_number,
        "card_account_id": str(card_account.id),
        "card_id": str(card.id),
        "amount": amount,
        "amount_usd": amount_usd,
        "ts": TS,
    }
    if conversion is not None:
        wire["conversion"] = conversion

    ledger_state = LedgerState(balance=balance, processed=frozenset())
    account_decision = account_decide(paying_account.account_number, wire, ledger_state, now=TS)

    settings = Settings()
    transaction_repository = PostgresTransactionRepository(session)
    applied_rate_repository = PostgresAppliedRateRepository(session)
    transaction_consumer = TransactionConsumer(settings, transaction_repository, applied_rate_repository)
    for produced in account_decision.account_events:
        await transaction_consumer._apply(json.dumps(produced).encode())

    card_movement_result = None
    if account_decision.card_events:
        card_payment_received = account_decision.card_events[0]
        card_state = card_domain.CardState(used_credit=used_credit, processed=frozenset())
        card_decision = card_domain.decide(card_state, card_payment_received, now=dt.datetime.now(dt.timezone.utc))

        movement_repository = PostgresCardMovementRepository(session)
        installment_repository = PostgresInstallmentRepository(session)
        card_movement_consumer = CardMovementConsumer(
            settings, movement_repository, installment_repository, applied_rate_repository
        )
        for produced in card_decision.card_events:
            await card_movement_consumer._apply(json.dumps(produced).encode())
        card_movement_result = card_decision

    transaction_rows = (
        await session.execute(
            select(TransactionORM).where(TransactionORM.request_id == uuid.UUID(request_id))
        )
    ).scalars().all()
    movement_rows = (
        await session.execute(
            select(CardMovementORM).where(CardMovementORM.request_id == uuid.UUID(request_id))
        )
    ).scalars().all()

    return account_decision, card_movement_result, transaction_rows, movement_rows


def _run(coro):
    return asyncio.run(coro)


# --- acceptance scenario 1: same-currency payment ----------------------------


def test_same_currency_payment_full_pipeline(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _run_pipeline(
                session, paying_currency="USD", amount=20000, balance=100000, used_credit=50000,
            )

    account_decision, card_decision, transaction_rows, movement_rows = _run(scenario())

    assert account_decision.new_balance == 80000
    debit_row = next(r for r in transaction_rows if r.type == "debit")
    assert debit_row.applied_rate_id is None

    assert card_decision.new_used_credit == 30000
    assert len(movement_rows) == 1
    assert movement_rows[0].movement_type == "payment"
    assert movement_rows[0].amount == Decimal("200.00")


# --- acceptance scenario 2: EUR payment links applied_rate -------------------


def test_cross_currency_payment_links_applied_rate_on_debit_leg(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _run_pipeline(
                session, paying_currency="EUR", amount=20000, balance=100000, used_credit=50000,
            )

    account_decision, card_decision, transaction_rows, movement_rows = _run(scenario())

    debit_row = next(r for r in transaction_rows if r.type == "debit")
    assert debit_row.applied_rate_id is not None

    expected = convert(20000, "EUR", "USD", "debit", RATES)
    assert card_decision.card_events[0]["amount_usd"] == expected["final_amount"]


# --- acceptance scenario 3: overpayment drives used_credit negative ----------


def test_overpayment_drives_used_credit_negative_end_to_end(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _run_pipeline(
                session, paying_currency="USD", amount=15000, balance=100000, used_credit=10000,
            )

    _, card_decision, _, movement_rows = _run(scenario())

    assert card_decision.new_used_credit == -5000
    assert movement_rows[0].movement_type == "payment"


# --- acceptance scenario 4: insufficient funds — zero card-side effects -----


def test_insufficient_funds_produces_zero_card_events_and_zero_movement_rows(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _run_pipeline(
                session, paying_currency="USD", amount=20000, balance=100, used_credit=50000,
            )

    account_decision, card_decision, transaction_rows, movement_rows = _run(scenario())

    assert account_decision.new_balance is None
    assert account_decision.card_events == ()
    assert card_decision is None
    assert [r.type for r in transaction_rows] == ["declined"]
    assert movement_rows == []
