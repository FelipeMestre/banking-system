"""RED/GREEN for Group C2 (`credit-cards-frontend-page`): Postgres integration
for `IAppliedRateRepository.get_by_id`, real DB via `fx_test_dsn`."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from openbankapi.infra.database.repositories.postgres_applied_rate_repository import (
    PostgresAppliedRateRepository,
)
from openbankapi.tests.db_fixtures import rollback_session


async def _insert_then_read(dsn: str):
    async with rollback_session(dsn) as session:
        repo = PostgresAppliedRateRepository(session)
        new_id = await repo.insert(
            pair="EUR/USD", mid_rate=1.1, applied_rate=1.1727, margin=0.05,
            direction="credit", source_ts=datetime.now(timezone.utc),
        )
        found = await repo.get_by_id(uuid.UUID(new_id))
        missing = await repo.get_by_id(uuid.uuid4())
        return new_id, found, missing


def test_get_by_id_reads_back_the_inserted_row(fx_test_dsn):
    new_id, found, missing = asyncio.run(_insert_then_read(fx_test_dsn))

    assert found is not None
    assert str(found.id) == new_id
    assert found.pair == "EUR/USD"
    assert float(found.applied_rate) == 1.1727
    assert missing is None
