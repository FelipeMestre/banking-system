"""Pure account-processing logic for the Flink account service (spec §5.3).

This module deliberately has no PyFlink imports: every decision the ledger makes
is a pure function of (account, event, current state), so it can be unit tested
without a Flink cluster. `job.py` owns the Flink wiring and keeps this module
free of runtime concerns.

All amounts are integer cents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

# --- event types (spec §4) ---------------------------------------------------

TRANSFER_REQUESTED = "transfer_requested"
OUTGOING_PAYMENT = "outgoing_payment"
INCOMING_PAYMENT = "incoming_payment"
DECLINED_PAYMENT = "declined_payment"

STATUS_APPROVED = "approved"
STATUS_DECLINED = "declined"

REASON_INSUFFICIENT_FUNDS = "insufficient_funds"
REASON_INVALID_AMOUNT = "invalid_amount"

# A single transfer touches up to three accounts, so a request_id alone is not a
# unique unit of work. The "leg" says which side of the transfer an event is, and
# (request_id, leg) is what deduplication is actually keyed on. Without it, a
# transfer whose destination and fees accounts are the same account would have
# its second credit silently swallowed as a duplicate.
LEG_DEBIT = "debit"
LEG_CREDIT_DESTINATION = "credit:destination"
LEG_CREDIT_FEES = "credit:fees"
LEG_CREDIT_SEED = "credit:seed"


def dedup_key(request_id: str, leg: str) -> str:
    return f"{request_id}:{leg}"


@dataclass(frozen=True)
class LedgerState:
    """The per-account keyed state, as a value object.

    `balance` is None for an account that has never been seen before.
    """

    balance: Optional[int]
    processed: FrozenSet[str]

    def is_processed(self, key: str) -> bool:
        return key in self.processed


@dataclass(frozen=True)
class Decision:
    """What the operator should do with one event, as data.

    `new_balance` is None when the balance must be left untouched — which is not
    the same as setting it to 0.
    """

    new_balance: Optional[int] = None
    dedup_keys: Tuple[str, ...] = ()
    account_events: Tuple[Dict[str, Any], ...] = ()
    status_events: Tuple[Dict[str, Any], ...] = ()

    @staticmethod
    def noop() -> "Decision":
        return Decision()


def shard_key_of(event: Dict[str, Any]) -> str:
    """The Kafka message key / Flink partitioning key for an event (spec §3.1).

    `transfer_requested` carries no `account_id`: it is keyed by its source
    account, because the source is the account whose balance guards the transfer.
    Every other event names its own target account.
    """
    account_id = event.get("account_id")
    if account_id:
        return account_id
    return event["source_account"]


def decide(account: str, event: Dict[str, Any], state: LedgerState, now: str) -> Decision:
    """Decide what happens to `account` when `event` arrives. Pure."""
    event_type = event.get("type")

    if event_type == TRANSFER_REQUESTED:
        return _on_transfer_requested(account, event, state, now)
    if event_type == INCOMING_PAYMENT:
        return _on_incoming_payment(event, state)
    if event_type == OUTGOING_PAYMENT:
        # Loopback confirmation: the debit is now durably in this account's own
        # log. The balance was already reserved when the request was processed,
        # so there is nothing left to apply — this only triggers the
        # client-facing confirmation.
        return Decision(status_events=(_status(event, STATUS_APPROVED, account, now),))
    if event_type == DECLINED_PAYMENT:
        return Decision(
            status_events=(
                _status(event, STATUS_DECLINED, account, now, reason=event.get("reason")),
            )
        )

    return Decision.noop()


def _on_transfer_requested(
    account: str, event: Dict[str, Any], state: LedgerState, now: str
) -> Decision:
    request_id = event["request_id"]
    debit_key = dedup_key(request_id, LEG_DEBIT)

    # At-least-once redelivery of a request we already settled — approved or
    # declined — must not be reconsidered, or a decline could silently flip to an
    # approval once funds arrive.
    if state.is_processed(debit_key):
        return Decision.noop()

    amount = event["amount"]
    fee_amount = event["fee_amount"]

    if not _is_valid_amount(amount) or not _is_valid_amount(fee_amount, allow_zero=True):
        return Decision(
            dedup_keys=(debit_key,),
            account_events=(_declined(event, account, REASON_INVALID_AMOUNT, now),),
        )

    balance = state.balance or 0
    total = amount + fee_amount

    if balance < total:
        return Decision(
            dedup_keys=(debit_key,),
            account_events=(_declined(event, account, REASON_INSUFFICIENT_FUNDS, now),),
        )

    return Decision(
        new_balance=balance - total,
        dedup_keys=(debit_key,),
        account_events=(
            _outgoing(event, account, total, now),
            _incoming(event, event["destination_account"], amount, LEG_CREDIT_DESTINATION, now),
            _incoming(event, event["fees_account"], fee_amount, LEG_CREDIT_FEES, now),
        ),
    )


def _on_incoming_payment(event: Dict[str, Any], state: LedgerState) -> Decision:
    leg = event.get("leg", LEG_CREDIT_DESTINATION)
    key = dedup_key(event["request_id"], leg)

    if state.is_processed(key):
        return Decision.noop()

    return Decision(
        new_balance=(state.balance or 0) + event["amount"],
        dedup_keys=(key,),
    )


def _is_valid_amount(value: Any, allow_zero: bool = False) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value >= 0 if allow_zero else value > 0


# --- event builders (spec §4) ------------------------------------------------


def _outgoing(event: Dict[str, Any], account: str, amount: int, now: str) -> Dict[str, Any]:
    return {
        "type": OUTGOING_PAYMENT,
        "request_id": event["request_id"],
        "account_id": account,
        "amount": amount,
        "leg": LEG_DEBIT,
        "ts": now,
    }


def _incoming(
    event: Dict[str, Any], account: str, amount: int, leg: str, now: str
) -> Dict[str, Any]:
    return {
        "type": INCOMING_PAYMENT,
        "request_id": event["request_id"],
        "account_id": account,
        "amount": amount,
        "leg": leg,
        "ts": now,
    }


def _declined(event: Dict[str, Any], account: str, reason: str, now: str) -> Dict[str, Any]:
    return {
        "type": DECLINED_PAYMENT,
        "request_id": event["request_id"],
        "account_id": account,
        "reason": reason,
        "ts": now,
    }


def _status(
    event: Dict[str, Any],
    status: str,
    account: str,
    now: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "request_id": event["request_id"],
        "status": status,
        "account_id": account,
        "ts": now,
    }
    if reason:
        payload["reason"] = reason
    return payload
