"""`GET /purchases/{request_id}/status` and `WS /ws/purchases/{request_id}`
(Credit Cards Phase 2). Mirrors `test_transfer_status` / `test_transfer_router.py`'s
own status-endpoint tests: pushes a verdict directly into the registry (the
Kafka consumer's own translation is `test_card_movement_consumer.py`'s concern),
then exercises the HTTP/WebSocket surface for real via the Fake-repository
e2e harness.
"""
from __future__ import annotations

import uuid

from . import conftest


def test_unresolved_request_is_pending_not_404():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    response = harness.client.get(f"/purchases/{request_id}/status")

    assert response.status_code == 200
    assert response.json() == {"request_id": request_id, "status": "pending"}


def test_resolved_approval_is_returned():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    harness.client.app.state.purchase_status_registry.resolve(
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    response = harness.client.get(f"/purchases/{request_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == request_id
    assert body["status"] == "approved"


def test_resolved_decline_carries_a_reason():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    harness.client.app.state.purchase_status_registry.resolve(
        {
            "request_id": request_id, "status": "declined",
            "reason": "insufficient_credit", "ts": "2026-01-01T00:00:00Z",
        }
    )

    response = harness.client.get(f"/purchases/{request_id}/status")

    assert response.json()["reason"] == "insufficient_credit"


def test_purchase_status_registry_is_separate_from_transfer_status_registry():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    # Resolving on the TRANSFER registry must never leak into the purchase one.
    harness.registry.resolve(
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    response = harness.client.get(f"/purchases/{request_id}/status")

    assert response.json() == {"request_id": request_id, "status": "pending"}


def test_websocket_receives_an_already_resolved_verdict_immediately():
    harness = conftest.build()
    request_id = str(uuid.uuid4())
    harness.client.app.state.purchase_status_registry.resolve(
        {"request_id": request_id, "status": "approved", "ts": "2026-01-01T00:00:00Z"}
    )

    with harness.client.websocket_connect(f"/ws/purchases/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message["status"] == "approved"


def test_websocket_times_out_to_pending_when_never_resolved():
    harness = conftest.build()
    request_id = str(uuid.uuid4())

    with harness.client.websocket_connect(f"/ws/purchases/{request_id}") as websocket:
        message = websocket.receive_json()

    assert message == {"request_id": request_id, "status": "pending"}
