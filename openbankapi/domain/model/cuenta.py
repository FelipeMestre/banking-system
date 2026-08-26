"""An account: the aggregate root (spec §3.5)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

# The 16-digit account number is the Kafka partition key for every topic in §4,
# with no mapping table in between. It has to be well-formed by construction.
NUMERO_CUENTA_PATTERN = re.compile(r"^[0-9]{16}$")
NUMERO_CUENTA_LENGTH = 16


def is_valid_numero_cuenta(value: str) -> bool:
    return bool(NUMERO_CUENTA_PATTERN.match(value))


class EstadoCuenta(str, Enum):
    ACTIVA = "activa"
    BLOQUEADA = "bloqueada"
    CERRADA = "cerrada"


@dataclass(frozen=True)
class Cuenta:
    """An account.

    `saldo` is present but this aggregate does NOT own it. It is a read-model
    projection kept eventually consistent by the `account-balances` consumer
    (spec §3.6); Flink's keyed state is the source of truth. Nothing in the
    domain or the API may compute a new balance from this value and write it
    back — that would be a second, uncoordinated write path to the same fact,
    which is the distributed-transaction problem this whole design exists to
    avoid.
    """

    id: UUID
    numero_cuenta: str
    moneda: str
    cliente_id: UUID
    sucursal_id: UUID
    saldo: int
    estado: EstadoCuenta
    created_at: datetime
    updated_at: datetime

    @property
    def is_operable(self) -> bool:
        """Whether the account may take part in a transfer at all.

        A reference-data check only. Whether it has the *funds* is a question
        only Flink can answer, and asking it here would be reading a projection
        that is allowed to be stale.
        """
        return self.estado is EstadoCuenta.ACTIVA
