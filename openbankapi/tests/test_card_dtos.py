"""RED for Credit Cards Phase 1: card masking serializer + DTO validation (T20)."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.card_account_dto import (
    CardAccountCreateDTO,
    CardAccountStatusUpdateDTO,
    CardAccountUpdateDTO,
)
from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO, CardMaskedDTO, CardStatusUpdateDTO


def test_card_masked_dto_renders_only_the_last_four_digits():
    dto = CardMaskedDTO(
        id=uuid.uuid4(), card_account_id=uuid.uuid4(), card_number="1234567812345678",
        expiration_date=dt.date(2030, 1, 1), status="active",
    )
    dumped = dto.model_dump(mode="json")
    assert dumped["card_number"] == "•••• •••• •••• 5678"


def test_card_issued_dto_renders_the_full_unmasked_number():
    dto = CardIssuedDTO(
        id=uuid.uuid4(), card_account_id=uuid.uuid4(), card_number="1234567812345678",
        expiration_date=dt.date(2030, 1, 1), status="active",
    )
    dumped = dto.model_dump(mode="json")
    assert dumped["card_number"] == "1234567812345678"


def test_card_account_create_dto_requires_credit_limit():
    with pytest.raises(ValidationError):
        CardAccountCreateDTO(customer_id=uuid.uuid4(), paying_account_id=uuid.uuid4())


def test_card_account_create_dto_accepts_valid_payload():
    dto = CardAccountCreateDTO(
        customer_id=uuid.uuid4(), paying_account_id=uuid.uuid4(), credit_limit="1500.00"
    )
    assert dto.credit_limit == 1500


def test_card_account_update_dto_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        CardAccountUpdateDTO(credit_limit="1000", status="active")


def test_card_account_status_update_dto_validates_status_pattern():
    with pytest.raises(ValidationError):
        CardAccountStatusUpdateDTO(status="not-a-status")
    dto = CardAccountStatusUpdateDTO(status="blocked")
    assert dto.status == "blocked"


def test_card_status_update_dto_validates_status_pattern():
    with pytest.raises(ValidationError):
        CardStatusUpdateDTO(status="not-a-status")
    dto = CardStatusUpdateDTO(status="active")
    assert dto.status == "active"
