"""Purchase intake DTOs (Credit Cards Phase 2)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PurchaseRequestDTO(BaseModel):
    card_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str
    description: Optional[str] = None
    # Installment count: at least one (a plain single-shot purchase), at
    # most 24 — matches the design's worked installment-split example.
    installments: int = Field(default=1, ge=1, le=24)


class PurchaseAcceptedDTO(BaseModel):
    request_id: str
    status: str = "pending"


class PurchaseStatusDTO(BaseModel):
    """Mirrors `TransferStatusDTO`'s shape: the Flink job's `_status()` (card-service/domain.py)
    emits `reason`, not `decline_reason`, so the field name here matches the wire payload
    verbatim — same convention `transfer_dto.py`'s `TransferStatusDTO` already establishes."""

    request_id: str
    status: str
    reason: Optional[str] = None
    ts: Optional[str] = None
