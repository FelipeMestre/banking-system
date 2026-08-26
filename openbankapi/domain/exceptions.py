"""Domain errors.

These carry no HTTP status. Translating a domain failure into a status code is
the controller's job (spec §7.2) — the domain layer must stay usable from a
consumer, a CLI or a test that has no notion of HTTP.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base for every error this domain raises."""


class NotFoundError(DomainError):
    """A resource addressed by the caller does not exist. -> 404"""

    def __init__(self, entity: str, identifier: object):
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class LocacionNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("locacion", identifier)


class SucursalNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("sucursal", identifier)


class ClienteNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("cliente", identifier)


class CuentaNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("cuenta", identifier)


class ReferencedEntityNotFoundError(DomainError):
    """A foreign key in the request body points at nothing. -> 422

    Distinct from NotFoundError on purpose: the resource the caller *addressed*
    exists fine, it is a value inside their payload that is wrong, which is a
    validation failure rather than a bad URL (spec §11.4).
    """

    def __init__(self, field: str, identifier: object):
        self.field = field
        self.identifier = identifier
        super().__init__(f"referenced {field} does not exist: {identifier}")


class DuplicateError(DomainError):
    """A unique business key is already taken. -> 409"""

    def __init__(self, field: str, value: object):
        self.field = field
        self.value = value
        super().__init__(f"{field} already exists: {value}")


class DuplicateAccountNumberError(DuplicateError):
    def __init__(self, value: object):
        super().__init__("numero_cuenta", value)


class InvalidNumeroCuentaError(DomainError):
    """A 16-digit account number was expected. -> 400"""

    def __init__(self, value: object):
        self.value = value
        super().__init__(f"numero_cuenta must be 16 digits: {value!r}")


class AccountNotOperableError(DomainError):
    """The account exists but its estado forbids the operation. -> 409"""

    def __init__(self, numero_cuenta: str, estado: str):
        self.numero_cuenta = numero_cuenta
        self.estado = estado
        super().__init__(f"account {numero_cuenta} is {estado}")


class InsufficientFundsError(DomainError):
    """Raised only where a balance decision is legitimately local.

    The ledger itself never raises this: Flink decides funds, and it reports a
    decline as an event, not an exception. Kept because the spec names it and
    because a future synchronous path would need it.
    """
