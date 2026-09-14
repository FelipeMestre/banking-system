"""Withdrawal DTOs for POST /admin/withdrawals (admin-cash-withdrawals).

Mirrors `deposit_dto.py` exactly, except the response can also carry a
decline outcome — an ATM-style "declined" is a resolved, legitimate business
outcome, not an HTTP error (see `withdrawal_router.py`).
"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

AccountNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{16}$")]
Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]


class WithdrawalRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_number: AccountNumber
    amount: int
    currency: str
    reason: Optional[str] = Field(default=None, max_length=300)

    @field_validator("amount")
    @classmethod
    def check_amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def check_currency(cls, v: str) -> str:
        allowed = {"EUR", "GBP", "USD"}
        upper = v.upper().strip()
        if upper not in allowed:
            raise ValueError(f"currency must be one of {allowed}")
        return upper


class WithdrawalResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    approved: bool
    amount_applied: Optional[int] = None
    applied_rate: Optional[dict] = None
    new_balance: Optional[int] = None
    reason: Optional[str] = None
