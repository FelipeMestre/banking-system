"""Postgres implementation of `ICardAccountAdminActionRepository` (D1/D2).

`record()` only `flush()`s the caller's shared session — same Unit-of-Work
discipline `_base.py`'s module docstring documents for every other
repository here: no commit, no own transaction, no Kafka.
"""
from __future__ import annotations

from uuid import UUID

from ..schemas.models import CardAccountAdminActionORM
from ._base import PostgresRepository


class PostgresCardAccountAdminActionRepository(PostgresRepository):
    async def record(
        self,
        *,
        card_account_id: UUID,
        action: str,
        admin_id: str,
        reason: str | None,
        details: dict | None,
    ) -> None:
        row = CardAccountAdminActionORM(
            card_account_id=card_account_id,
            action=action,
            admin_id=admin_id,
            reason=reason,
            details=details,
        )
        self._session.add(row)
        await self._session.flush()
