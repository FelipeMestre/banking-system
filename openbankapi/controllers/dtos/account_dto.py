"""Account DTOs — and the single most important rule in this codebase.

`AccountUpdateDTO` DOES NOT DECLARE `balance`. Not optional, not excluded, not
validated away: absent (spec §3.5).

Adding it would create a second, uncoordinated write path to the account balance
— a fact that Kafka and Flink already own — which is precisely the
"distributed transaction across heterogeneous systems" problem this entire
architecture exists to avoid. The read model would then disagree with the ledger
and nothing would be able to say which one was right.

`extra="forbid"` means a client that sends `balance` anyway gets a 422 instead of
having it silently dropped, which satisfies spec §11.3 loudly rather than
quietly. There is no code path from this DTO to `accounts.balance`; the only writer
is `IAccountBalanceProjection`, and no controller is ever handed one.
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True,
                                          min_length=3, max_length=3)]
NumeroAccount = Annotated[str, StringConstraints(pattern=r"^[0-9]{16}$")]


class AccountCreateDTO(BaseModel):
    """`account_number` is absent here too: it is generated server-side because
    it becomes the Kafka partition key (spec §8.2)."""

    model_config = ConfigDict(extra="forbid")

    currency: Currency
    customer_id: UUID
    branch_id: UUID


class AccountUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Optional[Currency] = None
    branch_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, pattern="^(active|blocked|closed)$")


class AccountResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_number: str
    currency: str
    customer_id: UUID
    branch_id: UUID
    # Readable, never writable. Eventually consistent with the ledger (§3.6).
    balance: int
    status: str
