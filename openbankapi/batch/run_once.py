"""Batch composition root (Credit Cards Phase 4).

Builds its own lightweight composition root: `Settings.from_env()` plus the
same `create_engine`/`create_sessionmaker` pair `main.py` uses for the real
app's engine — but it does NOT import `openbankapi.main` or any
`Depends`-based provider from `config/dependencies.py`. Those providers are
request-scoped and need an ASGI request context this script never has; a
plain constructor-injection script avoids importing the whole FastAPI app
just to obtain a DB session (design's explicit decision).

`check_and_close_if_due` is the safety-critical piece: it always calls
`close_statement` with a computed `target_close_date`, never with `today`.
That is what makes a missed tick (the worker was down past `CLOSE_DAY`)
still record the INTENDED close date once it wakes up, instead of the day it
happened to run.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config.config import Settings
from ..domain.model import Statement
from ..domain.service.cycle_dates import next_close_date_after
from ..domain.service.statement_service import StatementService
from ..infra.database.config.session import create_engine, create_sessionmaker
from ..infra.database.interfaces.card_account_repository import ICardAccountRepository
from ..infra.database.interfaces.statement_repository import IStatementRepository
from ..infra.database.repositories.postgres_card_account_repository import PostgresCardAccountRepository
from ..infra.database.repositories.postgres_card_movement_repository import PostgresCardMovementRepository
from ..infra.database.repositories.postgres_card_repository import PostgresCardRepository
from ..infra.database.repositories.postgres_installment_repository import PostgresInstallmentRepository
from ..infra.database.repositories.postgres_statement_repository import PostgresStatementRepository


async def check_and_close_if_due(
    statement_service: StatementService,
    statements: IStatementRepository,
    card_accounts: ICardAccountRepository,
    card_account_id: UUID,
    today: date,
    close_day: int,
) -> Optional[Statement]:
    """Downtime-safe: computes `target_close_date` from the account's last
    close or issuance date and calls `close_statement` with THAT target,
    never with `today`. Loops to catch up every period still due as of
    `today` in this one invocation (multiple missed ticks in a row), so a
    second call the same day/hour finds nothing left to do — this is what
    makes the duplicate-tick scenario provable: the guard is exercised on
    both calls, not just present in code."""
    last_closed: Optional[Statement] = None
    while True:
        last = await statements.get_latest(card_account_id)
        if last is not None:
            # `next_close_date_after` is inclusive of its reference date —
            # start strictly AFTER the last close, or an already-closed
            # period would resolve to itself forever and never advance.
            reference = last.period_end + timedelta(days=1)
        else:
            reference = await card_accounts.get_issuance_date(card_account_id)
        target_close_date = next_close_date_after(reference, close_day)

        if target_close_date > today:
            return last_closed

        last_closed = await statement_service.close_statement(card_account_id, target_close_date)


async def run_once_with(
    statement_service: StatementService,
    statements: IStatementRepository,
    card_accounts: ICardAccountRepository,
    today: date,
    close_day: int,
) -> None:
    """Orchestration only — no I/O construction here, so this is fully
    testable against fakes without a real database."""
    await statement_service.run_due_date_check(today)
    for card_account_id in await card_accounts.list_active_ids():
        await check_and_close_if_due(
            statement_service, statements, card_accounts, card_account_id, today, close_day
        )


def _build_service(session: AsyncSession, settings: Settings) -> tuple[StatementService, IStatementRepository, ICardAccountRepository]:
    statements = PostgresStatementRepository(session)
    card_movements = PostgresCardMovementRepository(session)
    installments = PostgresInstallmentRepository(session)
    card_accounts = PostgresCardAccountRepository(session)
    cards = PostgresCardRepository(session)
    service = StatementService(
        statements, card_movements, installments, cards,
        credit_card_apr=settings.credit_card_apr,
        late_fee_amount=settings.late_fee_amount,
        minimum_payment_rate=settings.minimum_payment_rate,
        due_date_offset_days=settings.due_date_offset_days,
    )
    return service, statements, card_accounts


async def run_once() -> None:
    """Real entry point: `python -m openbankapi.batch.run_once`.

    Deliberately does not import `openbankapi.main` or `openbankapi.app` —
    only the DB session/engine construction and the repositories/service
    this script actually needs.
    """
    settings = Settings.from_env()
    engine = create_engine(settings.database_dsn)
    sessionmaker = create_sessionmaker(engine)
    try:
        async with sessionmaker.begin() as session:
            service, statements, card_accounts = _build_service(session, settings)
            await run_once_with(service, statements, card_accounts, date.today(), settings.close_day)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_once())
