"""Card account DTOs (Credit Cards Phase 1)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CardAccountCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    paying_account_id: UUID
    credit_limit: Decimal = Field(gt=0)
    reason: Optional[str] = Field(default=None, max_length=300)


class CardAccountUpdateDTO(BaseModel):
    """Updates `credit_limit`/`paying_account_id` only (spec: `PUT /card-accounts/{id}`)."""

    model_config = ConfigDict(extra="forbid")

    credit_limit: Optional[Decimal] = Field(default=None, gt=0)
    reason: Optional[str] = Field(default=None, max_length=300)

class CardAccountStatusUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(active|blocked|closed)$")
    reason: Optional[str] = Field(default=None, max_length=300)


class CardAccountRenewDTO(BaseModel):
    """`POST /card-accounts/{id}/cards` was bodiless before this change — now
    accepts an optional `reason` for the audit row (design D2)."""

    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=300)


class CardAccountResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    paying_account_id: UUID
    credit_limit: Decimal
    status: str
