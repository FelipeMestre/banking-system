"""RED for Withdrawal DTOs validation — mirrors test_deposit_dto.py."""
import pytest
from pydantic import ValidationError


def test_valid_same_currency_dto():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    dto = WithdrawalRequestDTO(
        account_number="1234567890123456", amount=45540, currency="EUR", reason="atm withdrawal"
    )
    assert dto.account_number == "1234567890123456"
    assert dto.amount == 45540
    assert dto.currency == "EUR"


def test_amount_must_be_positive_zero():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    with pytest.raises(ValidationError) as exc:
        WithdrawalRequestDTO(account_number="1234567890123456", amount=0, currency="EUR")
    assert "amount must be positive" in str(exc.value).lower()


def test_amount_must_be_positive_negative():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    with pytest.raises(ValidationError) as exc:
        WithdrawalRequestDTO(account_number="1234567890123456", amount=-1, currency="EUR")
    assert "amount must be positive" in str(exc.value).lower()


def test_account_number_pattern():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    with pytest.raises(ValidationError):
        WithdrawalRequestDTO(account_number="123", amount=1000, currency="EUR")
    with pytest.raises(ValidationError):
        WithdrawalRequestDTO(account_number="abcdefghijklmnop", amount=1000, currency="EUR")


def test_currency_enum():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    with pytest.raises(ValidationError):
        WithdrawalRequestDTO(account_number="1234567890123456", amount=1000, currency="JPY")
    for cur in ("EUR", "GBP", "USD"):
        dto = WithdrawalRequestDTO(account_number="1234567890123456", amount=1000, currency=cur)
        assert dto.currency == cur


def test_reason_too_long():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO

    with pytest.raises(ValidationError):
        WithdrawalRequestDTO(
            account_number="1234567890123456", amount=1000, currency="EUR", reason="x" * 301
        )
    dto = WithdrawalRequestDTO(
        account_number="1234567890123456", amount=1000, currency="EUR", reason="x" * 300
    )
    assert dto.reason == "x" * 300


def test_response_dto_approved_and_new_balance():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalResponseDTO

    resp = WithdrawalResponseDTO(
        request_id="r1", approved=True, amount_applied=45540, applied_rate=None, new_balance=54460
    )
    assert resp.approved is True
    assert resp.amount_applied == 45540
    assert resp.applied_rate is None
    assert resp.new_balance == 54460
    dumped = resp.model_dump(exclude_none=True)
    assert "applied_rate" not in dumped
    assert "reason" not in dumped


def test_response_dto_cross_currency_with_rate():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalResponseDTO

    rate = {
        "pair": "USD_EUR",
        "mid_rate": 0.92,
        "applied_rate": 0.9108,
        "margin": 0.01,
        "direction": "debit",
        "source_ts": "2026-09-09T12:00:00+00:00",
    }
    resp = WithdrawalResponseDTO(
        request_id="r1", approved=True, amount_applied=45540, applied_rate=rate, new_balance=54460
    )
    assert resp.applied_rate == rate
    dumped = resp.model_dump(exclude_none=True)
    assert dumped["applied_rate"] == rate


def test_response_dto_declined_has_no_amount_or_balance():
    from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalResponseDTO

    resp = WithdrawalResponseDTO(request_id="r1", approved=False, reason="insufficient_funds")
    assert resp.approved is False
    assert resp.amount_applied is None
    assert resp.new_balance is None
    dumped = resp.model_dump(exclude_none=True)
    assert "amount_applied" not in dumped
    assert "new_balance" not in dumped
    assert "applied_rate" not in dumped
    assert dumped["reason"] == "insufficient_funds"
