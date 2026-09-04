"""Constraint-violation translation (spec §11.4).

These exist because the unit fakes raised domain errors directly and therefore
never exercised the real translation — which was broken: the constraint name is
nested at `error.orig.__cause__.constraint_name` for asyncpg, and the original
extractor only looked one level deep. A 500 reached the client in a live run.
"""
from __future__ import annotations

import pytest

from openbankapi.domain.exceptions import (
    DuplicateAccountNumberError,
    DuplicateCardNumberError,
    DuplicateError,
    InvalidCardNumberError,
    ReferencedEntityNotFoundError,
)
from openbankapi.infra.database.errors import constraint_name_of, translate


class _AsyncpgError(Exception):
    """Shaped like asyncpg's ForeignKeyViolationError."""

    def __init__(self, constraint_name):
        self.constraint_name = constraint_name
        super().__init__(constraint_name)


class _DbapiError(Exception):
    """Shaped like SQLAlchemy's asyncpg DBAPI wrapper: no name of its own."""


class _IntegrityError(Exception):
    def __init__(self, orig):
        self.orig = orig
        super().__init__("integrity")


def _nested(constraint: str) -> _IntegrityError:
    """The real shape: IntegrityError.orig.__cause__.constraint_name."""
    inner = _AsyncpgError(constraint)
    wrapper = _DbapiError("wrapped")
    wrapper.__cause__ = inner
    return _IntegrityError(wrapper)


def test_the_constraint_name_is_found_through_the_wrapper():
    assert constraint_name_of(_nested("accounts_customer_id_fkey")) == "accounts_customer_id_fkey"


def test_a_foreign_key_violation_becomes_a_referenced_entity_error():
    error = translate(_nested("accounts_customer_id_fkey"), values={"customer_id": "x"})
    assert isinstance(error, ReferencedEntityNotFoundError)
    assert error.field == "customer_id"


@pytest.mark.parametrize("constraint,field", [
    ("branches_location_id_fkey", "location_id"),
    ("accounts_branch_id_fkey", "branch_id"),
])
def test_every_foreign_key_is_mapped(constraint, field):
    error = translate(_nested(constraint), values={field: "x"})
    assert isinstance(error, ReferencedEntityNotFoundError)
    assert error.field == field


def test_a_duplicate_account_number_is_its_own_error():
    """The account repository retries on this one and on nothing else."""
    error = translate(_nested("accounts_account_number_key"), values={"account_number": "1"})
    assert isinstance(error, DuplicateAccountNumberError)


def test_a_duplicate_business_key_is_a_conflict():
    error = translate(_nested("branches_code_key"), values={"code": "MVD01"})
    assert isinstance(error, DuplicateError)
    assert not isinstance(error, DuplicateAccountNumberError)


def test_a_duplicate_auth0_sub_is_a_conflict_not_a_500():
    """`customers_auth0_sub_key` was missing from `_UNIQUE_KEYS` — a lost race
    on auto-linking an unlinked identity fell to the `raise error` branch
    below and leaked a raw 500 instead of a clean 409 (amendment bugfix)."""
    error = translate(_nested("customers_auth0_sub_key"), values={"auth0_sub": "auth0|abc"})
    assert isinstance(error, DuplicateError)
    assert error.field == "auth0_sub"


def test_an_unrecognised_constraint_is_re_raised_not_flattened():
    """An unknown constraint is a bug, not a client error."""
    original = _nested("something_we_never_declared")
    with pytest.raises(Exception) as caught:
        translate(original, values={})
    assert caught.value is original


# --- Credit Cards Phase 1: T11 -----------------------------------------------


@pytest.mark.parametrize("constraint,field", [
    ("card_accounts_customer_id_fkey", "customer_id"),
    ("card_accounts_paying_account_id_fkey", "paying_account_id"),
    ("cards_card_account_id_fkey", "card_account_id"),
    ("statements_card_account_id_fkey", "card_account_id"),
    ("card_movements_card_id_fkey", "card_id"),
    ("card_movements_applied_rate_id_fkey", "applied_rate_id"),
    ("installments_card_movement_id_fkey", "card_movement_id"),
])
def test_every_credit_card_foreign_key_is_mapped(constraint, field):
    error = translate(_nested(constraint), values={field: "x"})
    assert isinstance(error, ReferencedEntityNotFoundError)
    assert error.field == field


def test_a_duplicate_card_number_is_its_own_error():
    """The card repository retries on this one and on nothing else."""
    error = translate(_nested("cards_card_number_key"), values={"card_number": "1234567812345678"})
    assert isinstance(error, DuplicateCardNumberError)
    assert not isinstance(error, DuplicateAccountNumberError)


def test_an_invalid_card_number_check_violation_is_its_own_error():
    error = translate(_nested("cards_card_number_check"), values={"card_number": "abc"})
    assert isinstance(error, InvalidCardNumberError)


@pytest.mark.parametrize("constraint", [
    "card_accounts_status_check",
    "cards_status_check",
    "statements_status_check",
    "card_movements_movement_type_check",
    "installments_status_check",
])
def test_status_check_constraints_are_not_mapped_and_re_raise(constraint):
    """A status CHECK violation reaching Postgres is a real bug — the service
    validates transitions before any write, so this must never be silently
    swallowed into a domain error (design decision)."""
    original = _nested(constraint)
    with pytest.raises(Exception) as caught:
        translate(original, values={})
    assert caught.value is original
