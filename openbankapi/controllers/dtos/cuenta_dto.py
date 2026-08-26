"""Account DTOs — and the single most important rule in this codebase.

`CuentaUpdateDTO` DOES NOT DECLARE `saldo`. Not optional, not excluded, not
validated away: absent (spec §3.5).

Adding it would create a second, uncoordinated write path to the account balance
— a fact that Kafka and Flink already own — which is precisely the
"distributed transaction across heterogeneous systems" problem this entire
architecture exists to avoid. The read model would then disagree with the ledger
and nothing would be able to say which one was right.

`extra="forbid"` means a client that sends `saldo` anyway gets a 422 instead of
having it silently dropped, which satisfies spec §11.3 loudly rather than
quietly. There is no code path from this DTO to `cuentas.saldo`; the only writer
is `ICuentaBalanceProjection`, and no controller is ever handed one.
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Moneda = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True,
                                          min_length=3, max_length=3)]
NumeroCuenta = Annotated[str, StringConstraints(pattern=r"^[0-9]{16}$")]


class CuentaCreateDTO(BaseModel):
    """`numero_cuenta` is absent here too: it is generated server-side because
    it becomes the Kafka partition key (spec §8.2)."""

    model_config = ConfigDict(extra="forbid")

    moneda: Moneda
    cliente_id: UUID
    sucursal_id: UUID


class CuentaUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moneda: Optional[Moneda] = None
    sucursal_id: Optional[UUID] = None
    estado: Optional[str] = Field(default=None, pattern="^(activa|bloqueada|cerrada)$")


class CuentaResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero_cuenta: str
    moneda: str
    cliente_id: UUID
    sucursal_id: UUID
    # Readable, never writable. Eventually consistent with the ledger (§3.6).
    saldo: int
    estado: str
