"""RED for FX-14: PostgresAppliedRateRepository — real Postgres, no mocking
the database (per this repo's own documented testing anti-pattern list)."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from openbankapi.config.dependencies import get_applied_rate_repository
from openbankapi.infra.database.repositories.postgres_applied_rate_repository import (
    PostgresAppliedRateRepository,
)
from openbankapi.infra.database.schemas.models import AppliedRateORM
from openbankapi.tests.db_fixtures import rollback_session


async def _insert_and_fetch(dsn: str):
    async with rollback_session(dsn) as session:
        repo = PostgresAppliedRateRepository(session)
        source_ts = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
        new_id = await repo.insert(
            pair="EUR_USD",
            mid_rate=1.1628,
            applied_rate=1.1744,
            margin=0.01,
            direction="debit",
            source_ts=source_ts,
        )
        row = (
            await session.execute(select(AppliedRateORM).where(AppliedRateORM.id == uuid.UUID(new_id)))
        ).scalar_one()
        return new_id, row


def test_insert_returns_uuid_string_and_persists_matching_row(fx_test_dsn):
    new_id, row = asyncio.run(_insert_and_fetch(fx_test_dsn))

    assert isinstance(new_id, str)
    uuid.UUID(new_id)  # raises ValueError if this is not a real UUID

    assert row.pair == "EUR_USD"
    assert row.mid_rate == Decimal("1.162800")
    assert row.applied_rate == Decimal("1.174400")
    assert row.margin == Decimal("0.0100")
    assert row.direction == "debit"
    assert row.source_ts == datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)


def test_dependency_wiring_returns_postgres_repository():
    class _FakeSession:
        pass

    repo = get_applied_rate_repository(_FakeSession())  # type: ignore[arg-type]
    assert isinstance(repo, PostgresAppliedRateRepository)
