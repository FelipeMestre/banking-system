"""Card payment intake DTOs (Credit Cards Phase 3).

`amount` is integer cents in the paying account's own currency — unlike
`PurchaseRequestDTO`'s `Decimal` dollars, there is no separate `currency`
field here: the router resolves the paying account's currency server-side,
never from the request body.

`source_account` names which of the caller's own accounts to debit. The
router still resolves it server-side (never trusts a client-supplied id
without an ownership check) — see `card_account_router.py::request_payment`.
"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

# Account identifiers are 16-digit numbers (spec §3.5, §5) — same constraint
# `transfer_dto.py`/`account_dto.py` each define locally for their own DTOs.
AccountNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{16}$")]


class CardPaymentRequestDTO(BaseModel):
    amount: int = Field(gt=0)
    source_account: AccountNumber


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
