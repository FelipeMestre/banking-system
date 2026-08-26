"""Contracts for `accounts` persistence.

Split into TWO ports on purpose, and this split is the architecture, not a
style preference:

- `IAccountRepository` is what controllers and services get. It has no way to
  write `balance`. Not "a validated-away way" — no method at all.
- `IAccountBalanceProjection` has the single method that can, and only the
  `account-balances` consumer is ever handed one (spec §3.5, §3.6).

A controller holding `IAccountRepository` therefore cannot reach the balance
writer even by mistake, because the capability is not on the object it has.
"""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from ....domain.model import Account
from .common import Page


class IAccountRepository(Protocol):
    async def create(
        self, *, currency: str, customer_id: UUID, branch_id: UUID
    ) -> Account:
        """Create an account with a server-generated `account_number`.

        The number is generated here rather than accepted from the client
        because it becomes the Kafka partition key — it has to be correct by
        construction, not by request validation (spec §8.2). Retries on a
        UNIQUE collision; a collision must never surface as a 500 (spec §11.1).
        """
        ...

    async def get_by_numero(self, account_number: str) -> Optional[Account]: ...

    async def list(self, *, limit: int, offset: int) -> Page[Account]: ...

    async def update(
        self,
        account_number: str,
        *,
        currency: Optional[str] = None,
        branch_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Optional[Account]:
        """Update mutable reference data. `balance` is not a parameter and never
        will be — see the module docstring."""
        ...

    async def close(self, account_number: str) -> Optional[Account]:
        """Soft delete: `status = 'closed'`."""
        ...


class IAccountBalanceProjection(Protocol):
    """The one capability that may write `balance`. Handed only to the consumer."""

    async def apply_balance(self, account_number: str, balance: int) -> bool:
        """Set the projected balance. Returns False if no such account row.

        An absent account is not an error: the ledger happily runs accounts that
        reference data has never heard of (the fees account before anyone
        creates it, say), and the read model simply has nothing to project onto.
        """
        ...
