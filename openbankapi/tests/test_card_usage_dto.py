"""RED/GREEN for Group C3 (`credit-cards-frontend-page`): `UsedCreditEstimateDTO`
and `CardMovementDTO`. `is_estimate` is the honesty-signal field the spec
requires — it MUST default true and MUST be present in every serialization."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from openbankapi.api.v1.dtos.card_usage_dto import CardMovementDTO, UsedCreditEstimateDTO


def test_used_credit_estimate_dto_defaults_is_estimate_true():
    dto = UsedCreditEstimateDTO(
        card_account_id=uuid.uuid4(),
        used_credit_estimate=Decimal("55.00"),
        credit_limit=Decimal("1000.00"),
        movement_count=2,
    )
    assert dto.is_estimate is True
    assert dto.currency == "USD"
    assert dto.model_dump()["is_estimate"] is True


def test_used_credit_estimate_dto_rejects_negative_used_credit():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UsedCreditEstimateDTO(
            card_account_id=uuid.uuid4(),
            used_credit_estimate=Decimal("-1.00"),
            credit_limit=Decimal("1000.00"),
            movement_count=0,
        )


def test_card_movement_dto_optional_fx_and_installment_fields_default_none():
    dto = CardMovementDTO(
        id=uuid.uuid4(),
        movement_type="purchase",
        amount=Decimal("50.00"),
        currency="USD",
        occurred_at=datetime.now(timezone.utc),
    )
    assert dto.fx_pair is None
    assert dto.fx_applied_rate is None
    assert dto.installment_count is None
    assert dto.installment_amount is None
    assert dto.decline_reason is None


def test_card_movement_dto_carries_fx_and_installment_data_when_present():
    now = datetime.now(timezone.utc)
    dto = CardMovementDTO(
        id=uuid.uuid4(),
        movement_type="purchase",
        amount=Decimal("58.64"),
        currency="USD",
        occurred_at=now,
        fx_pair="EUR/USD",
        fx_applied_rate=Decimal("1.1727"),
        installment_count=3,
        installment_amount=Decimal("19.55"),
    )
    assert dto.fx_pair == "EUR/USD"
    assert dto.fx_applied_rate == Decimal("1.1727")
    assert dto.installment_count == 3
    assert dto.installment_amount == Decimal("19.55")
