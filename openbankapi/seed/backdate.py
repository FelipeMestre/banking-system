"""Backdate helper — ONLY direct DB tweak, preserves event-sourcing."""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from openbankapi.infra.database.schemas.models import CardMovementORM, InstallmentORM


async def _wait_for_movements(sessionmaker, request_ids: list[str], timeout_seconds: int = 30) -> list[UUID]:
    """Polls for the movements Flink projects from `request_ids`. Returns the
    ids actually found — possibly fewer than requested if Flink hasn't
    caught up within `timeout_seconds`."""
    deadline = time.time() + timeout_seconds
    ids = [UUID(r) for r in request_ids]
    while time.time() < deadline:
        async with sessionmaker() as session:
            result = await session.execute(select(CardMovementORM.request_id).where(CardMovementORM.request_id.in_(ids)))
            found = {row[0] for row in result.all()}
            if len(found) >= len(ids):
                return list(found)
        await asyncio.sleep(2)
    async with sessionmaker() as session:
        result = await session.execute(select(CardMovementORM.request_id).where(CardMovementORM.request_id.in_(ids)))
        return [row[0] for row in result.all()]


async def backdate_movements(sessionmaker, request_ids: list[str]) -> None:
    if not request_ids:
        return
    found = await _wait_for_movements(sessionmaker, request_ids)
    if not found:
        print("[backdate] no movements found yet — skipping backdate (Flink may still be processing)")
        return
    backdate = datetime.now(timezone.utc) - timedelta(days=45)
    async with sessionmaker.begin() as session:
        for idx, rid in enumerate(request_ids):
            target = backdate + timedelta(days=idx, hours=idx)
            await session.execute(
                update(CardMovementORM)
                .where(CardMovementORM.request_id == UUID(rid))
                .values(occurred_at=target, created_at=target)
            )
            mov_id = await session.scalar(select(CardMovementORM.id).where(CardMovementORM.request_id == UUID(rid)))
            if mov_id is not None:
                await session.execute(
                    update(InstallmentORM)
                    .where(InstallmentORM.card_movement_id == mov_id)
                    .values(due_date=target.date())
                )
        print(f"[backdate] updated {len(request_ids)} movements to ~{backdate.date().isoformat()} (for batch late_fee)")


async def backdate_to_window(sessionmaker, request_ids: list[str], period_start: date, period_end: date) -> int:
    """Spreads each movement's `occurred_at`/`created_at` evenly across
    `[period_start, period_end]` so `sum_single_charge_purchases`/
    `sum_payments` (both `func.date(occurred) BETWEEN` checks) pick them up
    inside the intended billing cycle. Returns how many movements were
    actually found and backdated."""
    if not request_ids:
        return 0
    found = await _wait_for_movements(sessionmaker, request_ids)
    if not found:
        print("[backdate] no movements found yet — skipping window backdate (Flink may still be processing)")
        return 0
    span_days = max((period_end - period_start).days, 1)
    async with sessionmaker.begin() as session:
        for idx, rid in enumerate(request_ids):
            offset_days = idx % (span_days + 1)
            target_date = period_start + timedelta(days=offset_days)
            target = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=idx % 24)
            await session.execute(
                update(CardMovementORM)
                .where(CardMovementORM.request_id == UUID(rid))
                .values(occurred_at=target, created_at=target)
            )
    print(f"[backdate] {len(found)} movement(s) spread across {period_start.isoformat()}..{period_end.isoformat()}")
    return len(found)
