"""RED for Credit Cards Phase 1: domain exception hierarchy (T5)."""
from __future__ import annotations

from openbankapi.domain.exceptions import (
    CardAccountNotFoundError,
    CardNotFoundError,
    DomainError,
    DuplicateCardNumberError,
    DuplicateError,
    InvalidCardNumberError,
    InvalidCardStatusError,
    NotFoundError,
)


def test_card_account_not_found_is_a_not_found_error():
    error = CardAccountNotFoundError("id-1")
    assert isinstance(error, NotFoundError)
    assert "id-1" in str(error)


def test_card_not_found_is_a_not_found_error():
    error = CardNotFoundError("1234567812345678")
    assert isinstance(error, NotFoundError)
    assert "1234567812345678" in str(error)


def test_duplicate_card_number_is_a_duplicate_error():
    error = DuplicateCardNumberError("1234567812345678")
    assert isinstance(error, DuplicateError)
    assert error.field == "card_number"
    assert error.value == "1234567812345678"


def test_invalid_card_status_is_a_domain_error_not_not_found():
    error = InvalidCardStatusError("closed", "active")
    assert isinstance(error, DomainError)
    assert not isinstance(error, NotFoundError)


def test_invalid_card_number_is_a_domain_error():
    error = InvalidCardNumberError("abc")
    assert isinstance(error, DomainError)
    assert "abc" in str(error)
