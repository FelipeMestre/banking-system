"""RED for `CardPaymentRequestDTO`/`CardPaymentAcceptedDTO` (Credit Cards
Phase 3 — task 1). `amount` is integer cents, per design. `source_account`
names which of the caller's own accounts to debit — the router (not this
DTO) verifies ownership, per `card_account_router.py::request_payment`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.card_payment_dto import (
    CardPaymentAcceptedDTO,
    CardPaymentRequestDTO,
)

VALID_ACCOUNT = "1111222233334444"


def test_accepts_a_positive_integer_amount_in_cents():
    dto = CardPaymentRequestDTO(amount=20000, source_account=VALID_ACCOUNT)
    assert dto.amount == 20000
    assert dto.source_account == VALID_ACCOUNT


@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_non_positive_amounts(bad):
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount=bad, source_account=VALID_ACCOUNT)


def test_rejects_a_non_integer_amount():
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount="20000.50", source_account=VALID_ACCOUNT)


def test_requires_a_source_account():
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount=20000)


@pytest.mark.parametrize("bad", ["123", "not-an-account", "12345678901234567"])
def test_rejects_a_source_account_that_is_not_16_digits(bad):
    with pytest.raises(ValidationError):
        CardPaymentRequestDTO(amount=20000, source_account=bad)


def test_accepted_dto_defaults_to_pending_status():
    dto = CardPaymentAcceptedDTO(request_id="req-1")
    assert dto.status == "pending"
