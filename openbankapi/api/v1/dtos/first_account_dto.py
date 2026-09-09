"""Request DTOs for `POST /accounts/me` (amendment — auto-link unlinked identity).

Two DTOs, deliberately not one, because "required vs optional" here is not a
pure request-shape fact: whether KYC fields are required depends on
server-side state (does this Auth0 identity already have a linked Customer?),
which Pydantic alone cannot express on a single model. `FirstAccountCreateDTO`
is the loose wire shape every caller sends; the router re-validates it against
the strict `FirstAccountKycDTO` only on the never-linked-identity branch.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .customer_dto import IdentificationNumber, Name

MINIMUM_AGE_YEARS = 18


class FirstAccountCreateDTO(BaseModel):
    """Request body for `POST /accounts/me`. All fields optional at this
    level — the router validates presence conditionally, since it is only
    required when the caller's Auth0 identity has no linked Customer yet.

    `extra="ignore"`, deliberately unlike every other request DTO in this
    codebase: the spec requires `currency`/`branch_id` sent by any caller to
    be silently ignored, never rejected — the account is always USD at the
    server-resolved default branch regardless of what a client sends here.
    """

    model_config = ConfigDict(extra="ignore")

    identification_number: Optional[IdentificationNumber] = None
    first_name: Optional[Name] = None
    last_name: Optional[Name] = None
    date_of_birth: Optional[date] = Field(default=None, repr=False)
    gender: Optional[str] = Field(default=None, max_length=20, repr=False)


class FirstAccountKycDTO(BaseModel):
    """Strict re-validation applied only on the never-linked-identity branch."""

    model_config = ConfigDict(extra="forbid")

    identification_number: IdentificationNumber
    first_name: Name
    last_name: Name
    date_of_birth: date = Field(repr=False)
    gender: Optional[str] = Field(default=None, max_length=20, repr=False)

    @field_validator("date_of_birth")
    @classmethod
    def _must_be_at_least_18(cls, value: date) -> date:
        today = datetime.now(timezone.utc).date()
        had_birthday = (today.month, today.day) >= (value.month, value.day)
        age = today.year - value.year - (0 if had_birthday else 1)
        if age < MINIMUM_AGE_YEARS:
            raise ValueError(f"must be at least {MINIMUM_AGE_YEARS} years old")
        return value
