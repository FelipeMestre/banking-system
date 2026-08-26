"""Translate Postgres constraint violations into domain errors (spec §11.4).

Keyed on the constraint NAME the driver reports, never on message text: messages
are localised and reworded between versions, names are stable. `init.sql`
deliberately leaves Postgres to generate its default names (`<table>_<col>_key`,
`<table>_<col>_fkey`), which is what this table mirrors — renaming a constraint
there silently breaks the mapping here.

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
    DuplicateError,
    InvalidNumeroCuentaError,
    ReferencedEntityNotFoundError,
)

_FOREIGN_KEYS = {
    "sucursales_locacion_id_fkey": "locacion_id",
    "cuentas_cliente_id_fkey": "cliente_id",
    "cuentas_sucursal_id_fkey": "sucursal_id",
}

_UNIQUE_KEYS = {
    "sucursales_codigo_key": "codigo",
    "clientes_numero_identificacion_key": "numero_identificacion",
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

    if name == "cuentas_numero_cuenta_key":
        return DuplicateAccountNumberError(values.get("numero_cuenta"))

    if name in _UNIQUE_KEYS:
        field = _UNIQUE_KEYS[name]
        return DuplicateError(field, values.get(field))

    if name == "cuentas_numero_cuenta_check":
        return InvalidNumeroCuentaError(values.get("numero_cuenta"))

    # An unrecognised constraint is a real bug, not a client error. Re-raising
    # the original keeps the traceback instead of flattening it into a 4xx.
    raise error
