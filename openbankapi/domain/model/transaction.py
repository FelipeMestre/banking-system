"""A transaction: one row of the event-sourced read model (spec §3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class TransactionType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    DECLINED = "declined"


@dataclass(frozen=True)
class Transaction:
    id: UUID
    request_id: UUID
    account_number: str
    type: TransactionType
    amount: int
    counterparty_account: str
    decline_reason: Optional[str]
    ts: datetime
    applied_rate_id: Optional[UUID] = None
