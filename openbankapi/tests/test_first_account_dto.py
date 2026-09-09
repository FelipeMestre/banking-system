"""`POST /accounts/me` request DTOs for the auto-link amendment.

`FirstAccountCreateDTO` is the loose, all-optional wire shape (fields are only
required conditionally, when the caller's identity has no linked Customer yet
— a server-side fact a pure request-shape model cannot express). It re-uses
`customer_dto.py`'s `IdentificationNumber`/`Name` constrained types.

`FirstAccountKycDTO` is the strict re-validation applied only on that
unlinked branch: every KYC field is required except `gender`, and
`date_of_birth` must indicate an age of at least 18 as of today.
"""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from openbankapi.api.v1.dtos.first_account_dto import FirstAccountCreateDTO, FirstAccountKycDTO


def _today_minus_years(years: int) -> dt.date:
    today = dt.datetime.now(dt.timezone.utc).date()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        # Feb 29 birthdays on a non-leap target year.
        return today.replace(month=2, day=28, year=today.year - years)


def test_kyc_dto_rejects_a_date_of_birth_under_18():
    with pytest.raises(ValidationError):
        FirstAccountKycDTO(
            identification_number="ID-1", first_name="Jane", last_name="Doe",
            date_of_birth=_today_minus_years(17),
        )


def test_kyc_dto_accepts_exactly_18_today():
    dto = FirstAccountKycDTO(
        identification_number="ID-1", first_name="Jane", last_name="Doe",
        date_of_birth=_today_minus_years(18),
    )
    assert dto.date_of_birth == _today_minus_years(18)


def test_kyc_dto_rejects_extra_fields():
    with pytest.raises(ValidationError):
        FirstAccountKycDTO(
            identification_number="ID-1", first_name="Jane", last_name="Doe",
            date_of_birth=_today_minus_years(30), unexpected="nope",
        )


def test_kyc_dto_requires_every_field_except_gender():
    with pytest.raises(ValidationError):
        FirstAccountKycDTO(first_name="Jane", last_name="Doe", date_of_birth=_today_minus_years(30))


def test_kyc_dto_gender_is_optional():
    dto = FirstAccountKycDTO(
        identification_number="ID-1", first_name="Jane", last_name="Doe",
        date_of_birth=_today_minus_years(30),
    )
    assert dto.gender is None


def test_create_dto_defaults_every_field_to_none():
    dto = FirstAccountCreateDTO()
    assert dto.identification_number is None
    assert dto.first_name is None
    assert dto.last_name is None
    assert dto.date_of_birth is None
    assert dto.gender is None


def test_create_dto_silently_ignores_extra_fields():
    """`extra="ignore"`, deliberately unlike every other request DTO here: the
    spec requires a client-sent `currency`/`branch_id` to be ignored, not
    rejected — the account is always USD at the server-resolved branch."""
    dto = FirstAccountCreateDTO(currency="EUR", branch_id="whatever")
    assert not hasattr(dto, "currency")
    assert dto.identification_number is None
