"""RED/GREEN for Group C2 (`credit-cards-frontend-page`): `IAppliedRateRepository.get_by_id`.

Unit test against the fake (fast path); the Postgres integration test lives
in `test_postgres_card_movement_and_installment_repository.py`'s sibling
suite via `test_postgres_applied_rate_get_by_id.py`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from openbankapi.tests.fakes import FakeAppliedRateRepository


def test_get_by_id_returns_the_inserted_row():
    async def _run():
        repo = FakeAppliedRateRepository()
        new_id = await repo.insert(
            pair="EUR/USD", mid_rate=1.1, applied_rate=1.1727, margin=0.05,
            direction="credit", source_ts=datetime.now(timezone.utc),
        )
        return await repo.get_by_id(uuid.UUID(new_id))

    rate = asyncio.run(_run())
    assert rate is not None
    assert rate.pair == "EUR/USD"
    assert rate.applied_rate == 1.1727


def test_get_by_id_returns_none_when_missing():
    async def _run():
        repo = FakeAppliedRateRepository()
        return await repo.get_by_id(uuid.uuid4())

    assert asyncio.run(_run()) is None
