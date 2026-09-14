"""Postgres implementation of IAppliedRateRepository (FX-14).

`PostgresAppliedRateRepository` is request-scoped, same as every other
`PostgresRepository` (flush only, caller owns the commit). `PostgresAppliedRateWriter`
below is the FX-19 counterpart to `PostgresTransactionWriter`: `TransactionConsumer`
runs off a Kafka thread, not an HTTP request, so it has no request-scoped
session to share and needs a writer that opens and commits its own session
per call instead.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from ....domain.model import AppliedRate
from ..schemas.models import AppliedRateORM
from ._base import PostgresRepository


def _to_domain(row: AppliedRateORM) -> AppliedRate:
    return AppliedRate(
        id=row.id, pair=row.pair, mid_rate=row.mid_rate, applied_rate=row.applied_rate,
        margin=row.margin, direction=row.direction, source_ts=row.source_ts,
        # `applied_rates` has no dedicated creation-timestamp column of its
        # own (see AppliedRateORM) — `source_ts`, the quote's own timestamp,
        # is the closest real value and is what the domain field represents
        # here, same as the fake's construction.
        created_at=row.source_ts,
    )


class PostgresAppliedRateRepository(PostgresRepository):
    async def get_by_id(self, applied_rate_id: UUID) -> Optional[AppliedRate]:
        row = await self._fetch_one(AppliedRateORM, AppliedRateORM.id == applied_rate_id)
        return _to_domain(row) if row is not None else None

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


class PostgresAppliedRateWriter:
    """The write side `TransactionConsumer` is handed (FX-19), mirroring
    `PostgresTransactionWriter`'s own per-call session for the same reason."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

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
        async with self._sessionmaker.begin() as session:
            repository = PostgresAppliedRateRepository(session)
            return await repository.insert(
                pair=pair, mid_rate=mid_rate, applied_rate=applied_rate,
                margin=margin, direction=direction, source_ts=source_ts,
            )
