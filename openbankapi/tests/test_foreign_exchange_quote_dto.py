"""RED for FX-13: quote DTOs — response never leaks internal pricing fields."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.foreign_exchange_quote_dto import (
    ForeignExchangeQuoteRequestDTO,
    ForeignExchangeQuoteResponseDTO,
)


def test_response_dto_excludes_internal_pricing_fields():
    forbidden = {"mid_rate", "margin", "pair", "direction", "source_ts"}
    fields = set(ForeignExchangeQuoteResponseDTO.model_fields.keys())
    assert forbidden.isdisjoint(fields)
    assert fields == {"final_amount", "from_currency", "to_currency", "applied_rate"}


def test_request_dto_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        ForeignExchangeQuoteRequestDTO(
            amount=0, from_currency="EUR", to_currency="USD", customer_effect="debit"
        )


def test_request_dto_rejects_invalid_customer_effect():
    with pytest.raises(ValidationError):
        ForeignExchangeQuoteRequestDTO(
            amount=1000, from_currency="EUR", to_currency="USD", customer_effect="refund"
        )


def test_request_dto_accepts_valid_payload():
    dto = ForeignExchangeQuoteRequestDTO(
        amount=10000, from_currency="EUR", to_currency="USD", customer_effect="credit"
    )
    assert dto.amount == 10000
    assert dto.customer_effect == "credit"
