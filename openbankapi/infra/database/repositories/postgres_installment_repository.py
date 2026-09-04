"""Postgres implementation of `IInstallmentRepository` (Credit Cards Phase 2)."""
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.model import Installment, InstallmentStatus
from ..schemas.models import InstallmentORM
from ._base import PostgresRepository


def _to_domain(row: InstallmentORM) -> Installment:
    return Installment(
        id=row.id,
        card_movement_id=row.card_movement_id,
        installment_number=row.installment_number,
        amount=row.amount,
        due_date=row.due_date,
        status=InstallmentStatus(row.status),
        created_at=row.created_at,
    )


class PostgresInstallmentRepository(PostgresRepository):
    async def bulk_insert(self, installments: List[Installment]) -> None:
        if not installments:
            return
        values = [
            {
                "id": installment.id,
                "card_movement_id": installment.card_movement_id,
                "installment_number": installment.installment_number,
                "amount": installment.amount,
                "due_date": installment.due_date,
                "status": installment.status.value,
            }
            for installment in installments
        ]
        await self._session.execute(pg_insert(InstallmentORM), values)
        await self._session.flush()

    async def get_by_movement_id(self, movement_id: UUID) -> List[Installment]:
        result = await self._session.execute(
            select(InstallmentORM)
            .where(InstallmentORM.card_movement_id == movement_id)
            .order_by(InstallmentORM.installment_number.asc())
        )
        return [_to_domain(row) for row in result.scalars().all()]


class PostgresInstallmentWriter:
    """The write side `CardMovementConsumer` is handed (Credit Cards Phase 2),
    mirroring `PostgresCardMovementWriter`'s own per-call session for the same
    reason (a Kafka-thread caller, not an HTTP request)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def bulk_insert(self, installments: List[Installment]) -> None:
        async with self._sessionmaker.begin() as session:
            await PostgresInstallmentRepository(session).bulk_insert(installments)

    async def get_by_movement_id(self, movement_id: UUID) -> List[Installment]:
        async with self._sessionmaker.begin() as session:
            return await PostgresInstallmentRepository(session).get_by_movement_id(movement_id)
