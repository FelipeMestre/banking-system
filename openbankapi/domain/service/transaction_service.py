"""Paginated retrieval over the transactions read model (spec §3.3).

Plain domain object, same shape as the other services here: no FastAPI, no
`Depends`. Its Dep wiring lives in `config/dependencies.py`.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from ...infra.database.interfaces.transaction_repository import ITransactionRepository
from ..model import Transaction


@dataclass(frozen=True)
class TransactionsPage:
    items: List[Transaction]
    next_cursor: Optional[str]


def _encode_cursor(ts: dt.datetime, transaction_id: UUID) -> str:
    return f"{ts.isoformat()}_{transaction_id}"


def _decode_cursor(cursor: str) -> tuple[dt.datetime, UUID]:
    """Raises `ValueError` on a malformed cursor — the caller decides how to
    turn that into an HTTP response; this layer only knows the encoding."""
    ts_part, _, id_part = cursor.rpartition("_")
    if not ts_part or not id_part:
        raise ValueError(f"malformed cursor: {cursor!r}")
    return dt.datetime.fromisoformat(ts_part), UUID(id_part)


class TransactionService:
    def __init__(self, repository: ITransactionRepository):
        self._repository = repository

    async def list_for_account(
        self, account_number: str, *, limit: int, cursor: Optional[str]
    ) -> TransactionsPage:
        before = _decode_cursor(cursor) if cursor else None
        items = await self._repository.list_by_account(account_number, limit=limit, before=before)
        next_cursor = _encode_cursor(items[-1].ts, items[-1].id) if len(items) == limit else None
        return TransactionsPage(items=items, next_cursor=next_cursor)
