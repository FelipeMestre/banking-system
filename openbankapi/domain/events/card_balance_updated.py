"""Card balance projection event (card-balances topic)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class CardBalanceUpdated:
    """Snapshot of a card account's used_credit, as produced by the Flink job.

    Consumed, never produced, by OpenBankAPI. Carries no `request_id`: the
    `card-balances` topic is compacted, so a record is the current value for
    a key rather than a fact about a purchase, and it cannot be replayed or
    deduplicated like a ledger event. `used_credit` is raw int cents, negative
    allowed (overpayment), no clamp.
    """

    card_account_id: str
    used_credit: int
    ts: str

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "CardBalanceUpdated":
        """Narrow an untrusted record off the topic. Raises on a bad shape."""
        card_account_id = payload["card_account_id"]
        used_credit = payload["used_credit"]
        if not isinstance(card_account_id, str) or not isinstance(used_credit, int):
            raise ValueError(f"malformed card balance record: {payload!r}")
        # bool is subclass of int, reject bool
        if isinstance(used_credit, bool):
            raise ValueError(f"malformed card balance record: {payload!r}")
        return CardBalanceUpdated(
            card_account_id=card_account_id,
            used_credit=used_credit,
            ts=str(payload.get("ts", "")),
        )
