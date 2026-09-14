"""RED for FX-16: `applied_rate_id` threading through the real Postgres
transaction repositories — no mocking the database (per this repo's own
documented testing anti-pattern list).

Both `PostgresTransactionRepository` (the DI-exposed, request-scoped class)
and `PostgresTransactionWriter` (what `TransactionConsumer` is actually wired
to in `main.py`) are exercised, because the design flagged that a change
touching only one of them would compile but never fire in production.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from sqlalchemy import select

from openbankapi.infra.database.config.session import create_sessionmaker
from openbankapi.infra.database.repositories.postgres_applied_rate_repository import (
    PostgresAppliedRateRepository,
)
from openbankapi.infra.database.repositories.postgres_transaction_repository import (
    PostgresTransactionRepository,
    PostgresTransactionWriter,
)
from openbankapi.infra.database.schemas.models import TransactionORM
from openbankapi.tests.db_fixtures import rollback_session

ACCOUNT_A = "1111111111111111"
ACCOUNT_B = "2222222222222222"


async def _insert_applied_rate(session) -> uuid.UUID:
    repo = PostgresAppliedRateRepository(session)
    new_id = await repo.insert(
        pair="EUR_USD",
        mid_rate=1.1628,
        applied_rate=1.1512,
        margin=0.01,
        direction="credit",
        source_ts=dt.datetime(2026, 9, 3, 12, 0, 0, tzinfo=dt.timezone.utc),
    )
    return uuid.UUID(new_id)


async def _repository_scenario(dsn: str):
    async with rollback_session(dsn) as session:
        rate_id = await _insert_applied_rate(session)
        repo = PostgresTransactionRepository(session)
        request_id = uuid.uuid4()
        await repo.insert(
            request_id=request_id, account_number=ACCOUNT_A, type="credit",
            amount=1074, counterparty_account=ACCOUNT_B, decline_reason=None,
            ts=dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc), applied_rate_id=rate_id,
        )
        row = (
            await session.execute(
                select(TransactionORM).where(TransactionORM.request_id == request_id)
            )
        ).scalar_one()
        return row.applied_rate_id, rate_id


async def _repository_scenario_none(dsn: str):
    async with rollback_session(dsn) as session:
        repo = PostgresTransactionRepository(session)
        request_id = uuid.uuid4()
        await repo.insert(
            request_id=request_id, account_number=ACCOUNT_A, type="debit",
            amount=1125, counterparty_account=ACCOUNT_B, decline_reason=None,
            ts=dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc),
        )
        row = (
            await session.execute(
                select(TransactionORM).where(TransactionORM.request_id == request_id)
            )
        ).scalar_one()
        return row.applied_rate_id


async def _writer_scenario(dsn: str):
    from openbankapi.infra.database.config.session import create_engine
    from openbankapi.infra.database.schemas.models import AppliedRateORM

    engine = create_engine(dsn)
    try:
        # The writer opens and commits its own session per call (it is not
        # request-scoped), so its FK target must be committed on a real,
        # autocommitting connection too — `rollback_session` would roll the
        # applied-rate row back out before the writer's own insert ever ran.
        async with engine.begin() as conn:
            result = await conn.execute(
                AppliedRateORM.__table__.insert().values(
                    pair="EUR_USD", mid_rate=1.1628, applied_rate=1.1512,
                    margin=0.01, direction="credit",
                    source_ts=dt.datetime(2026, 9, 3, 12, 0, 0, tzinfo=dt.timezone.utc),
                ).returning(AppliedRateORM.id)
            )
            rate_id = result.scalar_one()

        sessionmaker = create_sessionmaker(engine)
        writer = PostgresTransactionWriter(sessionmaker)
        request_id = uuid.uuid4()
        await writer.insert(
            request_id=request_id, account_number=ACCOUNT_A, type="credit",
            amount=1074, counterparty_account=ACCOUNT_B, decline_reason=None,
            ts=dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc), applied_rate_id=rate_id,
        )
        query_sessionmaker = create_sessionmaker(engine)
        async with query_sessionmaker() as query_session:
            row = (
                await query_session.execute(
                    select(TransactionORM).where(TransactionORM.request_id == request_id)
                )
            ).scalar_one()
            applied_rate_id = row.applied_rate_id
        # Clean up: both inserts above committed on a real connection, so
        # this test tidies up its own rows rather than relying on rollback.
        async with engine.begin() as conn:
            await conn.execute(
                TransactionORM.__table__.delete().where(TransactionORM.request_id == request_id)
            )
            await conn.execute(
                AppliedRateORM.__table__.delete().where(AppliedRateORM.id == rate_id)
            )
        return applied_rate_id, rate_id
    finally:
        await engine.dispose()


def test_postgres_transaction_repository_persists_applied_rate_id(fx_test_dsn):
    persisted_id, rate_id = asyncio.run(_repository_scenario(fx_test_dsn))
    assert persisted_id == rate_id


def test_postgres_transaction_repository_defaults_applied_rate_id_to_none(fx_test_dsn):
    persisted_id = asyncio.run(_repository_scenario_none(fx_test_dsn))
    assert persisted_id is None


def test_postgres_transaction_writer_persists_applied_rate_id(fx_test_dsn):
    persisted_id, rate_id = asyncio.run(_writer_scenario(fx_test_dsn))
    assert persisted_id == rate_id
