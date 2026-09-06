"""RED for Task 3.1 — Deposit DTOs validation."""
import pytest
from pydantic import ValidationError


def test_valid_same_currency_dto():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    dto = DepositRequestDTO(account_number="1234567890123456", amount=50000, currency="EUR", reason="cash branch 42")
    assert dto.account_number == "1234567890123456"
    assert dto.amount == 50000
    assert dto.currency == "EUR"


def test_amount_must_be_positive_zero():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    with pytest.raises(ValidationError) as exc:
        DepositRequestDTO(account_number="1234567890123456", amount=0, currency="EUR")
    assert "amount must be positive" in str(exc.value).lower()


def test_amount_must_be_positive_negative():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    with pytest.raises(ValidationError) as exc:
        DepositRequestDTO(account_number="1234567890123456", amount=-1, currency="EUR")
    assert "amount must be positive" in str(exc.value).lower()


def test_account_number_pattern():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    with pytest.raises(ValidationError):
        DepositRequestDTO(account_number="123", amount=1000, currency="EUR")
    with pytest.raises(ValidationError):
        DepositRequestDTO(account_number="abcdefghijklmnop", amount=1000, currency="EUR")


def test_currency_enum():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    with pytest.raises(ValidationError):
        DepositRequestDTO(account_number="1234567890123456", amount=1000, currency="JPY")
    # valid ones
    for cur in ("EUR", "GBP", "USD"):
        dto = DepositRequestDTO(account_number="1234567890123456", amount=1000, currency=cur)
        assert dto.currency == cur


def test_reason_too_long():
    from openbankapi.api.v1.dtos.deposit_dto import DepositRequestDTO

    with pytest.raises(ValidationError):
        DepositRequestDTO(account_number="1234567890123456", amount=1000, currency="EUR", reason="x" * 301)
    # 300 is ok
    dto = DepositRequestDTO(account_number="1234567890123456", amount=1000, currency="EUR", reason="x" * 300)
    assert dto.reason == "x" * 300


def test_response_dto_approved_and_new_balance():
    from openbankapi.api.v1.dtos.deposit_dto import DepositResponseDTO

    resp = DepositResponseDTO(request_id="r1", approved=True, amount_applied=50000, applied_rate=None, new_balance=150000)
    assert resp.approved is True
    assert resp.amount_applied == 50000
    assert resp.applied_rate is None
    assert resp.new_balance == 150000
    # omit-null should not include applied_rate when None
    dumped = resp.model_dump(exclude_none=True)
    assert "applied_rate" not in dumped


def test_response_dto_cross_currency_with_rate():
    from openbankapi.api.v1.dtos.deposit_dto import DepositResponseDTO

    rate = {"pair": "USD_EUR", "mid_rate": 0.92, "applied_rate": 0.9108, "margin": 0.01, "direction": "credit", "source_ts": "2026-09-03T12:00:00+00:00"}
    resp = DepositResponseDTO(request_id="r1", approved=True, amount_applied=45540, applied_rate=rate, new_balance=145540)
    assert resp.applied_rate == rate
    dumped = resp.model_dump(exclude_none=True)
    assert dumped["applied_rate"] == rate
