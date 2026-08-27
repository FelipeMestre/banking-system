"""The transfer request domain event (spec §5)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransferRequested:
    """A request to move money, before any ledger has seen it.

    Deliberately not a dict and deliberately not JSON: the wire shape from §5 is
    produced by `infra/kafka/repositories`, so the domain never depends on how this
    happens to be encoded on a topic.
    """

    request_id: str
    source_account: str
    destination_account: str
    fees_account: str
    amount: int
    fee_amount: int
    ts: str

    @property
    def total_debit(self) -> int:
        """What actually leaves the source account."""
        return self.amount + self.fee_amount
