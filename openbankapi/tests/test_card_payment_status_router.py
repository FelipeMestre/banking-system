"""`GET /payments/{request_id}/status` and `WS /ws/payments/{request_id}`
(Credit Cards Phase 3 — task 13). Mirrors `test_purchase_status_router.py`
exactly, on the payment domain's own `card_payment_status_registry`.
"""
from __future__ import annotations

import uuid

from . import conftest


def test_unresolved_request_is_pending_not_404():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    response = harness.client.get(f"/payments/{request_id}/status")

    assert response.status_code == 200
    assert response.json() == {"request_id": request_id, "status": "pending"}


def test_resolved_approval_is_returned():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    response = harness.client.get(f"/payments/{request_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == request_id
    assert body["status"] == "approved"


def test_card_payment_status_registry_is_isolated_from_purchase_and_transfer():
    """Resolving on the TRANSFER or PURCHASE registries must never leak into
    the card-payment one (spec: card-payment-status-api — dedicated registry
    isolation, no cross-talk)."""
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )
    conftest.resolve_sync(harness.client.app.state.purchase_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    response = harness.client.get(f"/payments/{request_id}/status")

    assert response.json() == {"request_id": request_id, "status": "pending"}


def test_websocket_receives_an_already_resolved_verdict_immediately():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message["status"] == "approved"


def test_websocket_times_out_to_pending_when_never_resolved():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message == {"request_id": request_id, "status": "pending"}


def test_get_status_prefers_settlement_over_the_authorization_verdict():
    """Once `CardMovementConsumer` has settled a payment, GET must report
    `settled` — never fall back to the (now-stale) `approved` verdict."""
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )
    conftest.resolve_sync(harness.client.app.state.card_payment_settlement_registry, 
        {"request_id": request_id, "status": "settled", "ts": "2026-01-01T00:00:01Z"}
    )

    response = harness.client.get(f"/payments/{request_id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "settled"


def test_get_status_is_approved_when_not_yet_settled():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    response = harness.client.get(f"/payments/{request_id}/status")

    assert response.json()["status"] == "approved"


def test_websocket_sends_the_settled_message_after_the_approved_verdict():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )
    conftest.resolve_sync(harness.client.app.state.card_payment_settlement_registry, 
        {"request_id": request_id, "status": "settled", "ts": "2026-01-01T00:00:01Z"}
    )

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert first["status"] == "approved"
    assert second["status"] == "settled"


def test_websocket_sends_only_the_declined_verdict_never_waits_on_settlement():
    """A decline never reaches `CardMovementConsumer` — waiting on the
    settlement registry here would just burn the timeout for nothing."""
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "declined", "reason": "insufficient_funds", "ts": "2026-01-01T00:00:00Z"}
    )

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        message = websocket.receive_json()
        websocket.close()

    assert message["status"] == "declined"


def test_websocket_closes_after_approved_alone_when_settlement_never_arrives():
    """Mirrors the existing pending-timeout behavior: an approved payment that
    never settles within the timeout still closes cleanly after delivering
    what it has, rather than hanging forever."""
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    conftest.resolve_sync(harness.client.app.state.card_payment_status_registry, 
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    with harness.client.websocket_connect(f"/ws/payments/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message["status"] == "approved"
