"""Postgres implementation of IAppliedRateRepository (FX-14).

Not called by any route in this phase — built and ready for a future phase
that needs to persist a margin-adjusted quote after the fact.
"""
from __future__ import annotations

from datetime import datetime

from ..schemas.models import AppliedRateORM
from ._base import PostgresRepository


class PostgresAppliedRateRepository(PostgresRepository):
    async def insert(
        self,
        *,
        pair: str,
        mid_rate: float,
        applied_rate: float,
        margin: float,
        direction: str,
        source_ts: datetime,
    ) -> str:
        row = await self._insert(
            AppliedRateORM,
            {
                "pair": pair,
                "mid_rate": mid_rate,
                "applied_rate": applied_rate,
                "margin": margin,
                "direction": direction,
                "source_ts": source_ts,
            },
        )
        return str(row.id)
