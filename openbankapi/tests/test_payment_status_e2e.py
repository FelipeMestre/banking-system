"""RED for Credit Cards Phase 3 — payment status pipeline e2e (task 17).

Drives the REAL account-service `domain.decide()` output straight into the
REAL `card_payment_status_registry`/router (mirroring `test_payment_status_
pipeline_integration.py`'s "compose the real pieces" approach for the
domain layer, and `test_purchase_status_router.py`'s established HTTP/
WebSocket harness for the status surface) — the two pieces this codebase's
own Kafka consumer thread would otherwise bridge in production.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from . import conftest

_ACCOUNT_SERVICE_DIR = Path(__file__).resolve().parents[2] / "account-service"
if str(_ACCOUNT_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_ACCOUNT_SERVICE_DIR))

from domain import LedgerState  # noqa: E402
from domain import decide as account_decide  # noqa: E402

TS = "2026-09-04T12:00:00Z"


def _payment_requested(request_id: str, amount: int) -> dict:
    return {
        "type": "payment_requested",
        "request_id": request_id,
        "destination_account": "4111111111111111",
        "card_account_id": "card-acct-1",
        "card_id": "card-1",
        "amount": amount,
        "ts": TS,
    }


def test_approved_payment_resolves_pending_to_approved_over_the_real_status_surface():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    decision = account_decide(
        "acc-pay", _payment_requested(request_id, amount=20000), LedgerState(balance=50000, processed=frozenset()), now=TS
    )
    assert len(decision.card_status_events) == 1

    # Before resolution: pending, exactly like `purchase-status`'s own contract.
    pending_response = harness.client.get(f"/payments/{request_id}/status")
    assert pending_response.json() == {"request_id": request_id, "status": "pending"}

    # The real domain output feeds the real registry the way
    # `CardPaymentStatusConsumer._dispatch` would in production.
    harness.client.app.state.card_payment_status_registry.resolve(decision.card_status_events[0])

    resolved_response = harness.client.get(f"/payments/{request_id}/status")
    assert resolved_response.json()["status"] == "approved"
    assert resolved_response.json()["request_id"] == request_id


def test_declined_payment_never_resolves_the_card_payment_status_registry():
    """Negative assertion (spec: kafka-topics — Only approved status reaches
    card-payment-status): an insufficient-funds decline produces ZERO
    `card_status_events`, so the registry for that `request_id` must stay
    unresolved forever — `GET .../status` keeps returning `pending`."""
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    decision = account_decide(
        "acc-pay", _payment_requested(request_id, amount=20000), LedgerState(balance=100, processed=frozenset()), now=TS
    )
    assert decision.card_status_events == ()
    assert decision.card_events == ()

    response = harness.client.get(f"/payments/{request_id}/status")
    assert response.json() == {"request_id": request_id, "status": "pending"}


def test_websocket_resolves_immediately_once_the_real_decision_is_applied():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    decision = account_decide(
        "acc-pay", _payment_requested(request_id, amount=5000), LedgerState(balance=50000, processed=frozenset()), now=TS
    )
    harness.client.app.state.card_payment_status_registry.resolve(decision.card_status_events[0])

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message["status"] == "approved"
