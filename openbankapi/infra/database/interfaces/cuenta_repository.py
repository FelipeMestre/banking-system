"""Contracts for `cuentas` persistence.

Split into TWO ports on purpose, and this split is the architecture, not a
style preference:

- `ICuentaRepository` is what controllers and services get. It has no way to
  write `saldo`. Not "a validated-away way" — no method at all.
- `ICuentaBalanceProjection` has the single method that can, and only the
  `account-balances` consumer is ever handed one (spec §3.5, §3.6).

A controller holding `ICuentaRepository` therefore cannot reach the balance
writer even by mistake, because the capability is not on the object it has.
"""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Cuenta
from .common import Page


class ICuentaRepository(Protocol):
    async def create(
        self, *, moneda: str, cliente_id: UUID, sucursal_id: UUID
    ) -> Cuenta:
        """Create an account with a server-generated `numero_cuenta`.

        The number is generated here rather than accepted from the client
        because it becomes the Kafka partition key — it has to be correct by
        construction, not by request validation (spec §8.2). Retries on a
        UNIQUE collision; a collision must never surface as a 500 (spec §11.1).
        """
        ...

    async def get_by_numero(self, numero_cuenta: str) -> Optional[Cuenta]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Cuenta]: ...

    async def update(
        self,
        numero_cuenta: str,
        *,
        moneda: Optional[str] = None,
        sucursal_id: Optional[UUID] = None,
        estado: Optional[str] = None,
    ) -> Optional[Cuenta]:
        """Update mutable reference data. `saldo` is not a parameter and never
        will be — see the module docstring."""
        ...

    async def close(self, numero_cuenta: str) -> Optional[Cuenta]:
        """Soft delete: `estado = 'cerrada'`."""
        ...


class ICuentaBalanceProjection(Protocol):
    """The one capability that may write `saldo`. Handed only to the consumer."""

    async def apply_balance(self, numero_cuenta: str, balance: int) -> bool:
        """Set the projected balance. Returns False if no such account row.

        An absent account is not an error: the ledger happily runs accounts that
        reference data has never heard of (the fees account before anyone
        creates it, say), and the read model simply has nothing to project onto.
        """
        ...
