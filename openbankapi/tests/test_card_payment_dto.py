"""RED for `CardPaymentRequestDTO`/`CardPaymentAcceptedDTO` (Credit Cards
Phase 3 — task 1). `amount` is integer cents, per design; no `paying_account_id`
field — the paying account is fixed on `card_accounts` from Phase 1."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.card_payment_dto import (
    CardPaymentAcceptedDTO,
    CardPaymentRequestDTO,
)


def test_accepts_a_positive_integer_amount_in_cents():
    dto = CardPaymentRequestDTO(amount=20000)
    assert dto.amount == 20000


@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_non_positive_amounts(bad):
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount=bad)


def test_rejects_a_non_integer_amount():
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount="20000.50")


def test_accepted_dto_defaults_to_pending_status():
    dto = CardPaymentAcceptedDTO(request_id="req-1")
    assert dto.status == "pending"
