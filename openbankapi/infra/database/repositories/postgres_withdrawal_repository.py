"""Postgres implementation of IWithdrawalRepository.

Uses `ON CONFLICT DO NOTHING` on `movement_id` (unique) — same idempotency
reasoning as `PostgresDepositRepository` and every other writer in this
codebase: at-least-once Kafka redelivery is routine, not theoretical.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..schemas.models import WithdrawalORM
from ._base import PostgresRepository


class PostgresWithdrawalRepository(PostgresRepository):
    async def insert(
        self,
        *,
        movement_id: UUID,
        admin_id: str,
        reason: Optional[str] = None,
    ) -> None:
        statement = (
            pg_insert(WithdrawalORM)
            .values(movement_id=movement_id, admin_id=admin_id, reason=reason)
            .on_conflict_do_nothing(index_elements=["movement_id"])
        )
        await self._session.execute(statement)
        await self._session.flush()


class PostgresWithdrawalWriter:
    """The write side `TransactionConsumer` is handed for withdrawal audit rows.

    Deliberately NOT a `PostgresRepository`: consumer calls arrive off a Kafka
    thread, not an HTTP request, so there is no request-scoped session to share
    (same split as `PostgresDepositWriter`). Opens and commits its own session
    per call.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def insert(
        self,
        *,
        movement_id: UUID,
        admin_id: str,
        reason: Optional[str] = None,
    ) -> None:
        statement = (
            pg_insert(WithdrawalORM)
            .values(movement_id=movement_id, admin_id=admin_id, reason=reason)
            .on_conflict_do_nothing(index_elements=["movement_id"])
        )
        async with self._sessionmaker.begin() as session:
            await session.execute(statement)
