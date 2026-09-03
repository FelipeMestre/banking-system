"""RED for FX-16..FX-20: end-to-end transfer conversion, real Postgres, no DB
mocking (per this repo's own documented testing anti-pattern list).

`account-service` is a separate Flink job, not a process this test suite can
start — but its ledger decision logic (`domain.decide`) is pure Python with
zero PyFlink imports (that is the whole point of the module's own docstring),
so this test drives the real pipeline end to end by composing the three real
pieces directly: `TransferService.request_transfer` (produces the wire
event), `domain.decide` (the real ledger rules, imported straight from
`account-service/domain.py`), and `TransactionConsumer._apply` (the real
event-to-row translation, backed by real Postgres repositories).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import func, select

from openbankapi.config import Settings
from openbankapi.domain.service.transfer_service import TransferService
from openbankapi.infra.database.repositories.postgres_account_repository import PostgresAccountRepository
from openbankapi.infra.database.repositories.postgres_applied_rate_repository import (
    PostgresAppliedRateRepository,
)
from openbankapi.infra.database.repositories.postgres_transaction_repository import (
    PostgresTransactionRepository,
)
from openbankapi.infra.database.schemas.models import AccountORM, AppliedRateORM, BranchORM, CustomerORM, LocationORM
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer
from openbankapi.tests.db_fixtures import rollback_session
from openbankapi.tests.fakes import FakePublisher

_ACCOUNT_SERVICE_DIR = Path(__file__).resolve().parents[2] / "account-service"
if str(_ACCOUNT_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_ACCOUNT_SERVICE_DIR))

from domain import LedgerState, decide  # noqa: E402

TS = "2026-09-03T12:00:00Z"
RATES = {"EUR": 0.8613, "GBP": 0.74}


class FixedRatesCacheService:
    def __init__(self, rates: Optional[Dict[str, float]] = None):
        self.rates = rates if rates is not None else RATES

    async def get_rates(self) -> Dict[str, float]:
        return dict(self.rates)


async def _seed_account(session, *, currency: str, balance: int = 0) -> str:
    """A committed-to-the-session reference-data trio: location, branch,
    customer, account — mirroring what `POST /accounts` would create."""
    location = LocationORM(name="Test HQ", active=True)
    session.add(location)
    await session.flush()

    branch = BranchORM(code=f"B{uuid.uuid4().hex[:6]}", name="Test Branch", location_id=location.id, active=True)
    session.add(branch)
    await session.flush()

    customer = CustomerORM(
        identification_number=str(uuid.uuid4().int)[:15],
        first_name="Test", last_name="Customer",
        date_of_birth=dt.date(1990, 1, 1),
    )
    session.add(customer)
    await session.flush()

    account_number = str(abs(hash(uuid.uuid4())) % (10**16)).rjust(16, "0")
    account = AccountORM(
        account_number=account_number, currency=currency,
        customer_id=customer.id, branch_id=branch.id, balance=balance, status="active",
    )
    session.add(account)
    await session.flush()
    return account_number


async def _settle_transfer(
    session, *, source_currency: str, destination_currency: str, amount: int,
    source_balance: int, fee_flat_cents: int = 25,
):
    """Runs the real pipeline: request -> ledger decision -> transaction rows.

    Returns (wire_event, decision, transactions_by_type).
    """
    source_account = await _seed_account(session, currency=source_currency, balance=source_balance)
    destination_account = await _seed_account(session, currency=destination_currency)

    settings = Settings(fee_flat_cents=fee_flat_cents, fees_account="0000000000000001")
    publisher = FakePublisher()
    account_repository = PostgresAccountRepository(session)
    cache_service = FixedRatesCacheService()
    service = TransferService(settings, publisher, account_repository, cache_service)

    await service.request_transfer(source_account, destination_account, amount)
    _, _, wire_event = publisher.published[0]

    state = LedgerState(balance=source_balance, processed=frozenset())
    decision = decide(source_account, wire_event, state, now=TS)

    transaction_repository = PostgresTransactionRepository(session)
    applied_rate_repository = PostgresAppliedRateRepository(session)
    consumer = TransactionConsumer(settings, transaction_repository, applied_rate_repository)

    for produced_event in decision.account_events:
        await consumer._apply(json.dumps(produced_event).encode())

    from openbankapi.infra.database.schemas.models import TransactionORM

    result = await session.execute(
        select(TransactionORM).where(TransactionORM.request_id == uuid.UUID(str(wire_event["request_id"])))
    )
    by_type: Dict[str, list] = {}
    for row in result.scalars().all():
        by_type.setdefault(row.type, []).append(row)

    applied_rate_count = await session.scalar(select(func.count()).select_from(AppliedRateORM))

    return wire_event, decision, by_type, applied_rate_count, source_account, destination_account


def _run(coro):
    return asyncio.run(coro)


# --- same-currency: unchanged behavior ----------------------------------------


def test_same_currency_transfer_produces_unchanged_transaction_rows(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _settle_transfer(
                session, source_currency="USD", destination_currency="USD",
                amount=1100, source_balance=5000,
            )

    wire_event, decision, by_type, applied_rate_count, _, _ = _run(scenario())

    assert "applied_rate" not in wire_event or wire_event["applied_rate"] is None
    debit = by_type["debit"][0]
    credit_destination = next(r for r in by_type["credit"] if r.amount == 1100)
    assert debit.applied_rate_id is None
    assert credit_destination.applied_rate_id is None
    assert applied_rate_count == 0


# --- EUR -> USD: full linkage --------------------------------------------------


def test_eur_to_usd_links_two_applied_rate_rows_and_matches_quote_math(fx_test_dsn):
    from openbankapi.domain.service.conversion_service import convert

    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _settle_transfer(
                session, source_currency="EUR", destination_currency="USD",
                amount=1100, source_balance=5000,
            )

    wire_event, decision, by_type, applied_rate_count, source_account, destination_account = _run(scenario())

    expected_destination = convert(1100, "EUR", "USD", "credit", RATES)
    expected_fee = convert(25, "EUR", "USD", "debit", RATES)

    debit = by_type["debit"][0]
    credit_rows = by_type["credit"]
    destination_credit = next(r for r in credit_rows if r.account_number == destination_account)
    fees_credit = next(r for r in credit_rows if r.account_number != destination_account)

    assert destination_credit.amount == expected_destination["final_amount"]
    assert fees_credit.amount == expected_fee["final_amount"]
    assert applied_rate_count == 2
    assert destination_credit.applied_rate_id is not None
    assert fees_credit.applied_rate_id is not None
    assert debit.applied_rate_id is None


# --- destination already USD, fee still converts -------------------------------


def test_eur_to_usd_destination_needs_no_conversion_but_fee_still_links(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _settle_transfer(
                session, source_currency="EUR", destination_currency="USD",
                amount=1100, source_balance=5000,
            )

    _, _, by_type, applied_rate_count, _, destination_account = _run(scenario())
    fees_credit = next(r for r in by_type["credit"] if r.account_number != destination_account)
    assert fees_credit.applied_rate_id is not None
    assert applied_rate_count == 2  # destination (EUR!=USD) + fee both convert


# --- USD -> EUR: no fee conversion ---------------------------------------------


def test_usd_to_eur_credits_fees_raw_with_zero_fee_leg_applied_rate_row(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _settle_transfer(
                session, source_currency="USD", destination_currency="EUR",
                amount=1100, source_balance=5000,
            )

    _, _, by_type, applied_rate_count, _, destination_account = _run(scenario())
    fees_credit = next(r for r in by_type["credit"] if r.account_number != destination_account)
    assert fees_credit.amount == 25  # raw fee_amount, unconverted
    assert fees_credit.applied_rate_id is None
    assert applied_rate_count == 1  # destination leg only


# --- declined: zero applied_rates rows -----------------------------------------


def test_declined_multicurrency_transfer_persists_no_applied_rate_rows(fx_test_dsn):
    async def scenario():
        async with rollback_session(fx_test_dsn) as session:
            return await _settle_transfer(
                session, source_currency="EUR", destination_currency="USD",
                amount=1100, source_balance=10,
            )

    wire_event, decision, by_type, applied_rate_count, _, _ = _run(scenario())

    assert [e["type"] for e in decision.account_events] == ["declined_payment"]
    assert by_type["declined"][0].applied_rate_id is None
    assert applied_rate_count == 0
