"""Pure card-purchase authorization logic for the Flink Card Service (design §2).

Zero PyFlink imports, zero currency-conversion imports: every decision is a
pure function of (card_state, event, now), so it is unit-testable without a
Flink cluster or Postgres — mirrors `account-service/domain.py`'s pattern.
`job.py` owns the Flink wiring and keeps this module free of runtime concerns.

All amounts are integer cents. `credit_limit` and `amount_usd` are read from
`event` on EVERY call — never from `CardState` — because Postgres remains the
source of truth for the limit (a human/admin could change it out-of-band)
while Flink owns only the derived running total (design §6, the single most
important correctness guarantee of this phase).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, FrozenSet, Optional, Tuple

PURCHASE_REQUESTED = "purchase_requested"

STATUS_APPROVED = "approved"
STATUS_DECLINED = "declined"

REASON_INSUFFICIENT_CREDIT = "insufficient_credit"


@dataclass(frozen=True)
class CardState:
    """Per-`card_id` keyed state, as a value object.

    Holds ONLY the running total ever reserved against the card — NEVER the
    credit limit, which always arrives fresh on the event itself.
    """

    used_credit: int
    processed: FrozenSet[str] = field(default_factory=frozenset)

    def is_processed(self, request_id: str) -> bool:
        return request_id in self.processed


@dataclass(frozen=True)
class Decision:
    """What the operator should do with one event, as data.

    `new_used_credit` is `None` when `used_credit` must be left untouched —
    a decline or a duplicate never mutates state.
    """

    new_used_credit: Optional[int] = None
    dedup_keys: Tuple[str, ...] = ()
    card_events: Tuple[Dict[str, Any], ...] = ()
    status_events: Tuple[Dict[str, Any], ...] = ()

    @staticmethod
    def noop() -> "Decision":
        return Decision()


def decide(card_state: CardState, event: Dict[str, Any], now: datetime) -> Decision:
    """Decide what happens when a `purchase_requested` event arrives for the
    card keyed by `event["card_id"]`. Pure."""
    request_id = event["request_id"]

    # At-least-once redelivery of a request already settled — approved or
    # declined — must not be reconsidered, or a decline could silently flip
    # to an approval once credit frees up.
    if card_state.is_processed(request_id):
        return Decision.noop()

    # Installments reserve the FULL amount immediately (spec §1.2): the
    # credit check always compares the full purchase total, never a
    # per-installment slice, regardless of `installments`.
    amount_usd = event["amount_usd"]
    credit_limit = event["credit_limit"]
    available = credit_limit - card_state.used_credit

    if amount_usd <= available:
        new_used_credit = card_state.used_credit + amount_usd
        return Decision(
            new_used_credit=new_used_credit,
            dedup_keys=(request_id,),
            card_events=(_approved(event, now),),
            status_events=(_status(event, STATUS_APPROVED, now),),
        )

    return Decision(
        dedup_keys=(request_id,),
        card_events=(_declined(event, now),),
        status_events=(_status(event, STATUS_DECLINED, now, reason=REASON_INSUFFICIENT_CREDIT),),
    )


def _approved(event: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    payload = {
        "type": "purchase_approved",
        "request_id": event["request_id"],
        "card_id": event["card_id"],
        "card_account_id": event["card_account_id"],
        "amount_usd": event["amount_usd"],
        "installments": event.get("installments", 1),
        "ts": now.isoformat(),
    }
    applied_rate = event.get("applied_rate")
    if applied_rate is not None:
        payload["applied_rate"] = applied_rate
    return payload


def _declined(event: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    return {
        "type": "purchase_declined",
        "request_id": event["request_id"],
        "card_id": event["card_id"],
        "card_account_id": event["card_account_id"],
        "amount_usd": event["amount_usd"],
        "decline_reason": REASON_INSUFFICIENT_CREDIT,
        "ts": now.isoformat(),
    }


def _status(
    event: Dict[str, Any], status: str, now: datetime, reason: Optional[str] = None
) -> Dict[str, Any]:
    payload = {
        "request_id": event["request_id"],
        "status": status,
        "ts": now.isoformat(),
    }
    if reason:
        payload["reason"] = reason
    return payload
