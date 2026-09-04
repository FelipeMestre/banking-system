"""Postgres implementation of `ICardMovementRepository` (Credit Cards Phase 2).

`insert` uses `ON CONFLICT DO NOTHING` rather than a pre-check SELECT — same
reasoning as `PostgresTransactionRepository`: at-least-once Kafka delivery
makes the race routine, not theoretical.
"""
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.model import CardMovement, CardMovementType
from ..schemas.models import CardMovementORM
from ._base import PostgresRepository


def _to_domain(row: CardMovementORM) -> CardMovement:
    return CardMovement(
        id=row.id,
        card_id=row.card_id,
        request_id=row.request_id,
        movement_type=CardMovementType(row.movement_type),
        amount=row.amount,
        currency=row.currency,
        created_at=row.created_at,
        description=row.description,
        decline_reason=row.decline_reason,
        applied_rate_id=row.applied_rate_id,
        occurred_at=row.occurred_at,
    )


class PostgresCardMovementRepository(PostgresRepository):
    async def insert(self, movement: CardMovement) -> CardMovement:
        statement = (
            pg_insert(CardMovementORM)
            .values(
                id=movement.id,
                card_id=movement.card_id,
                request_id=movement.request_id,
                movement_type=movement.movement_type.value,
                amount=movement.amount,
                currency=movement.currency,
                description=movement.description,
                decline_reason=movement.decline_reason,
                applied_rate_id=movement.applied_rate_id,
                occurred_at=movement.occurred_at,
            )
            .on_conflict_do_nothing(index_elements=["request_id", "movement_type"])
        )
        await self._session.execute(statement)
        await self._session.flush()
        # A redelivered event conflicts and inserts nothing — the existing row
        # (not `movement`) is the one whose generated id/created_at is real.
        result = await self._session.execute(
            select(CardMovementORM).where(
                CardMovementORM.request_id == movement.request_id,
                CardMovementORM.movement_type == movement.movement_type.value,
            )
        )
        row = result.scalar_one()
        return _to_domain(row)

    async def get_by_card_id(self, card_id: UUID) -> List[CardMovement]:
        result = await self._session.execute(
            select(CardMovementORM)
            .where(CardMovementORM.card_id == card_id)
            .order_by(CardMovementORM.created_at.desc())
        )
        return [_to_domain(row) for row in result.scalars().all()]


class PostgresCardMovementWriter:
    """The write side `CardMovementConsumer` is handed (Credit Cards Phase 2),
    mirroring `PostgresTransactionWriter`'s own per-call session: the consumer
    runs off a Kafka thread, not an HTTP request, so it has no request-scoped
    session to share."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def insert(self, movement: CardMovement) -> CardMovement:
        async with self._sessionmaker.begin() as session:
            return await PostgresCardMovementRepository(session).insert(movement)
