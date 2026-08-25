"""Request/response models for the gateway HTTP surface (spec §6)."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

AccountId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class TransferRequest(BaseModel):
    source_account: AccountId
    destination_account: AccountId
    # Integer cents. Anything at or below zero is not a transfer.
    amount: int = Field(gt=0, le=10**12)


class TransferAccepted(BaseModel):
    request_id: str
    status: str = "pending"
    fee_amount: int

