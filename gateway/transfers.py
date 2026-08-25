"""Pure transfer-request construction (spec §4, §6). All amounts in cents."""
from __future__ import annotations

from typing import Any, Dict


def compute_fee(amount: int, flat_fee_cents: int) -> int:
    """A flat fee, never larger than the amount being transferred.

    Capping at `amount` keeps the fee from quietly exceeding the transfer on
    very small payments, which would make the total debit more than double the
    amount the user actually asked to send.
    """
    return min(max(flat_fee_cents, 0), amount)


def build_transfer_requested(
    request_id: str,
    source_account: str,
    destination_account: str,
    fees_account: str,
    amount: int,
    fee_amount: int,
    now: str,
) -> Dict[str, Any]:
    return {
        "type": "transfer_requested",
        "request_id": request_id,
        "source_account": source_account,
        "destination_account": destination_account,
        "fees_account": fees_account,
        "amount": amount,
        "fee_amount": fee_amount,
        "ts": now,
    }
