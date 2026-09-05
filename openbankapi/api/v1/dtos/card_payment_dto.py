"""Card payment intake DTOs (Credit Cards Phase 3).

`amount` is integer cents in the paying account's own currency — unlike
`PurchaseRequestDTO`'s `Decimal` dollars, there is no separate `currency`
field here: the paying account is fixed on `card_accounts.paying_account_id`
(Phase 1) and the router resolves its currency server-side, never from the
request body.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CardPaymentRequestDTO(BaseModel):
    amount: int = Field(gt=0)


class CardPaymentAcceptedDTO(BaseModel):
    request_id: str
    status: str = "pending"


class CardPaymentStatusDTO(BaseModel):
    """Mirrors `PurchaseStatusDTO`'s shape: only `approved` is ever published
    to `card-payment-status` (spec: kafka-topics) — an insufficient-funds
    decline surfaces solely as the account-side `declined_payment`, never
    here."""

    request_id: str
    status: str
    reason: Optional[str] = None
    ts: Optional[str] = None
