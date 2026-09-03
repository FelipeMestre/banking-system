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
CHEAT_ACCOUNT = "cheatAccount"


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

    `balance_events` mirrors that write onto the `account-balances` topic (spec
    §3.6, §4.3). The read model cannot learn a balance any other way: the
    `transfer-status` feed only ever names the *source* account, so a credit
    landing on a destination or a fees account would otherwise be invisible to
    OpenBankAPI. The invariant every branch below upholds is exact — a branch
    that sets `new_balance` emits exactly one balance event carrying that
    post-change value, and a branch that leaves the balance alone (a decline, a
    duplicate, a loopback confirmation) emits none. Re-announcing an unchanged
    balance would misreport when the account last moved.
    """

    new_balance: Optional[int] = None
    dedup_keys: Tuple[str, ...] = ()
    account_events: Tuple[Dict[str, Any], ...] = ()
    status_events: Tuple[Dict[str, Any], ...] = ()
    balance_events: Tuple[Dict[str, Any], ...] = ()

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
        return _on_incoming_payment(account, event, state, now)
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

    if account == CHEAT_ACCOUNT:
        return Decision(
            new_balance=balance,
            dedup_keys=(debit_key,),
            account_events=(_outgoing(event, account, total, fee_amount, now),),
        )

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
            account_events=(_declined(event, account, REASON_INVALID_AMOUNT, now, amount),),
        )

    balance = state.balance or 0
    total = amount + fee_amount

    if balance < total and account != "":
        return Decision(
            dedup_keys=(debit_key,),
            account_events=(_declined(event, account, REASON_INSUFFICIENT_FUNDS, now, amount),),
        )

    # The reservation: the funds leave the source account here, before either
    # credit has been produced, which is what stops the same balance from being
    # promised twice.
    reserved = balance - total
    return Decision(
        new_balance=reserved,
        dedup_keys=(debit_key,),
        account_events=(
            _outgoing(event, account, total, fee_amount, now),
            _incoming(event, event["destination_account"], amount, LEG_CREDIT_DESTINATION, now),
            _incoming(event, event["fees_account"], fee_amount, LEG_CREDIT_FEES, now),
        ),
        balance_events=(_balance_updated(account, reserved, now),),
    )


def _on_incoming_payment(
    account: str, event: Dict[str, Any], state: LedgerState, now: str
) -> Decision:
    leg = event.get("leg", LEG_CREDIT_DESTINATION)
    key = dedup_key(event["request_id"], leg)

    if state.is_processed(key):
        return Decision.noop()

    # `account` rather than `event["account_id"]`: the balance record has to name
    # the account whose keyed state just moved, and that is the operator's key.
    credited = (state.balance or 0) + event["amount"]
    return Decision(
        new_balance=credited,
        dedup_keys=(key,),
        balance_events=(_balance_updated(account, credited, now),),
    )


def _is_valid_amount(value: Any, allow_zero: bool = False) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value >= 0 if allow_zero else value > 0


# --- event builders (spec §4) ------------------------------------------------


def _outgoing(
    event: Dict[str, Any], account: str, amount: int, fee_amount: int, now: str
) -> Dict[str, Any]:
    return {
        "type": OUTGOING_PAYMENT,
        "request_id": event["request_id"],
        "account_id": account,
        "amount": amount,
        "fee_amount": fee_amount,
        "destination_account": event["destination_account"],
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
        "source_account": event["source_account"],
        "leg": leg,
        "ts": now,
    }


def _declined(
    event: Dict[str, Any], account: str, reason: str, now: str, amount: int
) -> Dict[str, Any]:
    return {
        "type": DECLINED_PAYMENT,
        "request_id": event["request_id"],
        "account_id": account,
        "amount": amount,
        "destination_account": event["destination_account"],
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


def _balance_updated(account: str, balance: int, now: str) -> Dict[str, Any]:
    """A record for the `account-balances` topic (spec §3.6, §4.3).

    Deliberately not shaped like the `account-events` payloads: it carries no
    `request_id` and no `type`. The topic is compacted, so only the newest value
    per account survives — it is a snapshot of the current balance, not a fact
    about a transfer. Adding a `request_id` here would suggest the record could
    be deduplicated or replayed like a ledger event, and it cannot.
    """
    return {
        "account_id": account,
        "balance": balance,
        "ts": now,
    }
