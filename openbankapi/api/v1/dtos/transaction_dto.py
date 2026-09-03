"""Transaction DTOs (spec §3.3). The read model is response-only — no
`TransactionCreateDTO` exists, and none ever will: rows are written
exclusively by `TransactionConsumer`, never by an HTTP route.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ....infra.database.interfaces.common import DEFAULT_LIMIT, MAX_LIMIT


class TransactionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    type: str
    amount: int
    counterparty_account: str
    decline_reason: Optional[str] = None
    ts: datetime


class TransactionsPageParams(BaseModel):
    """Cursor-based, not limit/offset: the feed is unbounded and concurrent
    inserts must never skip or repeat a row (spec §3.3)."""

    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    cursor: Optional[str] = None


class TransactionsPageDTO(BaseModel):
    items: List[TransactionDTO]
    next_cursor: Optional[str] = None
