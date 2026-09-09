"""Translate Postgres constraint violations into domain errors (spec §11.4).

Keyed on the constraint NAME the driver reports, never on message text: messages
are localised and reworded between versions, names are stable. The baseline
Alembic migration deliberately leaves every constraint unnamed, so Postgres
generates its own default names (`<table>_<col>_key`, `<table>_<col>_fkey`),
which is what this table mirrors — naming a constraint there silently breaks
the mapping here.

Translating on the way out, rather than pre-checking with a SELECT, avoids a
time-of-check-to-time-of-use race: the row could vanish between the check and
the insert, and only the database can decide atomically.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError

from ...domain.exceptions import (
    DomainError,
    DuplicateAccountNumberError,
    DuplicateCardNumberError,
    DuplicateError,
    InvalidAccountNumberError,
    InvalidCardNumberError,
    ReferencedEntityNotFoundError,
)

_FOREIGN_KEYS = {
    "branches_location_id_fkey": "location_id",
    "accounts_customer_id_fkey": "customer_id",
    "accounts_branch_id_fkey": "branch_id",
    "card_accounts_customer_id_fkey": "customer_id",
    "card_accounts_paying_account_id_fkey": "paying_account_id",
    "cards_card_account_id_fkey": "card_account_id",
    "statements_card_account_id_fkey": "card_account_id",
    "card_movements_card_id_fkey": "card_id",
    "card_movements_applied_rate_id_fkey": "applied_rate_id",
    "installments_card_movement_id_fkey": "card_movement_id",
}

_UNIQUE_KEYS = {
    "branches_code_key": "code",
    "customers_identification_number_key": "identification_number",
    "customers_auth0_sub_key": "auth0_sub",
}


def constraint_name_of(error: BaseException) -> Optional[str]:
    """Find the constraint name anywhere in the exception chain.

    It is never at a fixed depth. SQLAlchemy's asyncpg dialect wraps the real
    `asyncpg.exceptions.ForeignKeyViolationError` inside its own DBAPI
    `IntegrityError`, so the name sits at `error.orig.__cause__.constraint_name`
    — while psycopg puts it on `.diag` of `error.orig` instead. Walking the
    chain covers both and does not break when a driver changes its nesting.
    """
    seen = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))

        name = getattr(current, "constraint_name", None)
        if name:
            return str(name)
        diag = getattr(current, "diag", None)
        if diag is not None and getattr(diag, "constraint_name", None):
            return str(diag.constraint_name)

        # `orig` first: that is SQLAlchemy's own wrapper link.
        nxt = getattr(current, "orig", None)
        current = nxt if nxt is not None and nxt is not current else current.__cause__
    return None


def translate(error: IntegrityError, *, values: Optional[dict] = None) -> DomainError:
    """Map an IntegrityError to the domain error a controller can act on."""
    values = values or {}
    name = constraint_name_of(error) or ""

    if name in _FOREIGN_KEYS:
        field = _FOREIGN_KEYS[name]
        return ReferencedEntityNotFoundError(field, values.get(field))

    if name == "accounts_account_number_key":
        return DuplicateAccountNumberError(values.get("account_number"))

    if name == "cards_card_number_key":
        return DuplicateCardNumberError(values.get("card_number"))

    if name in _UNIQUE_KEYS:
        field = _UNIQUE_KEYS[name]
        return DuplicateError(field, values.get(field))

    if name == "accounts_account_number_check":
        return InvalidAccountNumberError(values.get("account_number"))

    if name == "cards_card_number_check":
        return InvalidCardNumberError(values.get("card_number"))

    # An unrecognised constraint is a real bug, not a client error. Re-raising
    # the original keeps the traceback instead of flattening it into a 4xx.
    raise error
