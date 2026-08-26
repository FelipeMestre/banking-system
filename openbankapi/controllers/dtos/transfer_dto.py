"""Transfer DTOs (spec §8.1). Wire-compatible with v1 — the frontend is unchanged."""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

# Account identifiers are 16-digit numbers from v2 onward (spec §3.5, §5).
NumeroAccount = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{16}$")]


class TransferRequestDTO(BaseModel):
    source_account: NumeroAccount
    destination_account: NumeroAccount
    # Integer cents. Anything at or below zero is not a transfer.
    amount: int = Field(gt=0, le=10**12)


class TransferAcceptedDTO(BaseModel):
    request_id: str
    status: str = "pending"
    fee_amount: int


class TransferStatusDTO(BaseModel):
    request_id: str
    status: str
    account_id: Optional[str] = None
    reason: Optional[str] = None
    ts: Optional[str] = None
