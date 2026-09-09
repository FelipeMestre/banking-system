"""RED for Credit Cards Phase 2: `PurchaseRequestDTO` (T3.1)."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.purchase_dto import PurchaseRequestDTO


def _payload(**overrides):
    payload = {
        "card_id": str(uuid.uuid4()),
        "amount": "100.00",
        "currency": "USD",
        "description": "coffee",
    }
    payload.update(overrides)
    return payload


def test_installments_defaults_to_one():
    dto = PurchaseRequestDTO(**_payload())
    assert dto.installments == 1


def test_installments_rejects_zero():
    with pytest.raises(ValidationError):
        PurchaseRequestDTO(**_payload(installments=0))


def test_installments_rejects_twenty_five():
    with pytest.raises(ValidationError):
        PurchaseRequestDTO(**_payload(installments=25))


@pytest.mark.parametrize("installments", [1, 12, 24])
def test_installments_accepts_valid_range(installments):
    dto = PurchaseRequestDTO(**_payload(installments=installments))
    assert dto.installments == installments


def test_description_is_optional():
    payload = _payload()
    del payload["description"]
    dto = PurchaseRequestDTO(**payload)
    assert dto.description is None
