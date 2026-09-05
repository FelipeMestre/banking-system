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
CARD_PAYMENT_RECEIVED = "card_payment_received"

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
    # Credit Cards Phase 3: a payment's approval status routes to the NEW
    # `card-payment-status` topic, never `purchase-status` (`status_events`) —
    # kept as a separate field so `job.py` can sink each to its own topic
    # without inspecting event payloads (spec: kafka-topics).
    payment_status_events: Tuple[Dict[str, Any], ...] = ()

    @staticmethod
    def noop() -> "Decision":
        return Decision()


def decide(card_state: CardState, event: Dict[str, Any], now: datetime) -> Decision:
    """Event-type dispatcher (Credit Cards Phase 3 — design: "wrap, don't
    rewrite"). `purchase_requested` wraps the ORIGINAL, unmodified authorization
    logic as the first branch; `card_payment_received` is the new branch.
    An unrecognised type is a noop — `job.py`'s own allow-list filter is the
    first line of defense, this is the second (design's defensive style)."""
    event_type = event.get("type")

    if event_type == PURCHASE_REQUESTED:
        return _on_purchase_requested(card_state, event, now)
    if event_type == CARD_PAYMENT_RECEIVED:
        return _on_card_payment_received(card_state, event, now)

    return Decision.noop()


def _on_purchase_requested(card_state: CardState, event: Dict[str, Any], now: datetime) -> Decision:
    """Decide what happens when a `purchase_requested` event arrives for the
    card keyed by `event["card_id"]`. Pure. Unchanged body from before the
    Phase 3 dispatcher was introduced — only the function boundary moved."""
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


def _on_card_payment_received(card_state: CardState, event: Dict[str, Any], now: datetime) -> Decision:
    """A payment reduces `used_credit` unconditionally (Credit Cards Phase 3):
    NO credit-limit check, and overpayment is explicitly allowed to drive
    `used_credit` negative — the account side already verified the payer had
    the funds; this side only ever records the paydown (spec:
    card-service-payment-handling)."""
    request_id = event["request_id"]

    if card_state.is_processed(request_id):
        return Decision.noop()

    new_used_credit = card_state.used_credit - event["amount_usd"]
    return Decision(
        new_used_credit=new_used_credit,
        dedup_keys=(request_id,),
        card_events=(_payment_applied(event, now),),
        payment_status_events=(_status(event, STATUS_APPROVED, now),),
    )


def _payment_applied(event: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    return {
        "type": "payment_applied",
        "request_id": event["request_id"],
        "card_account_id": event["card_account_id"],
        "card_id": event["card_id"],
        "amount_usd": event["amount_usd"],
        "ts": now.isoformat(),
    }


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
