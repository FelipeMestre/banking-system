"""The balance projection event (spec §3.6, §4.3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class BalanceUpdated:
    """A snapshot of an account's balance, as produced by the Flink job.

    Consumed, never produced, by OpenBankAPI. It carries no `request_id`: the
    `account-balances` topic is compacted, so a record is the current value for
    a key rather than a fact about a transfer, and it cannot be replayed or
    deduplicated like a ledger event.
    """

    account_id: str
    balance: int
    ts: str

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "BalanceUpdated":
        """Narrow an untrusted record off the topic. Raises on a bad shape."""
        account_id = payload["account_id"]
        balance = payload["balance"]
        if not isinstance(account_id, str) or not isinstance(balance, int):
            raise ValueError(f"malformed balance record: {payload!r}")
        return BalanceUpdated(
            account_id=account_id,
            balance=balance,
            ts=str(payload.get("ts", "")),
        )
