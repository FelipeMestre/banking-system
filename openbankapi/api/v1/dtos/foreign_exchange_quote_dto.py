"""Quote DTOs for `POST /foreign-exchange-rates/quote` (FX-13).

`ForeignExchangeQuoteResponseDTO` deliberately has no `mid_rate`/`margin`/
`pair`/`direction`/`source_ts` field: those are internal pricing fields the
customer-facing response must never expose (spec FX-13). Only
`applied_rate["applied_rate"]` — the single already-margin-adjusted rate —
crosses into the response.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ForeignExchangeQuoteRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(gt=0)
    from_currency: str
    to_currency: str
    customer_effect: Literal["credit", "debit"]


class ForeignExchangeQuoteResponseDTO(BaseModel):
    final_amount: int
    from_currency: str
    to_currency: str
    applied_rate: Optional[float]
