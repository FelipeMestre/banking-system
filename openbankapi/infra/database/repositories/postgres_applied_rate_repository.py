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

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

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
