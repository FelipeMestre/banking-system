"""Card payment status endpoints (Credit Cards Phase 3). Mirrors
`purchase_status_router.py` exactly, on the payment domain's own
`StatusRegistry` (`CardPaymentStatusRegistryDep`) — never the transfer or
purchase one.

Same decisions the transfer/purchase status endpoints already establish,
deliberately unchanged here: an unresolved request is 200 `pending`, not 404
(the request exists and is in flight); the WebSocket times out rather than
being held open forever.

Two independent registries back this endpoint. `CardPaymentStatusRegistryDep`
carries the authorization verdict (`approved`/`declined`), published the
instant account-service debits the paying account. `CardPaymentSettlementRegistryDep`
is resolved separately, in-process, by `CardMovementConsumer` only once the
resulting `payment_applied` movement is actually durable in Postgres — the
point at which movements/current-cycle/statements are safe to reload. They
are read in that order (settlement first) rather than joined: a payment that
somehow never settles still correctly reports its verdict forever, instead of
the whole status getting stuck on one missing signal.
"""
from __future__ import annotations

import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from openbankapi.api.v1.dtos.card_payment_dto import CardPaymentStatusDTO
from openbankapi.config.dependencies import (
    CardPaymentSettlementRegistryDep,
    CardPaymentStatusRegistryDep,
    SettingsDep,
)

LOG = logging.getLogger("openbankapi.card_payment")
router = APIRouter(tags=["card-payments"])


@router.get(
    "/payments/{request_id}/status",
    response_model=CardPaymentStatusDTO,
    response_model_exclude_none=True,
)
async def card_payment_status(
    request_id: str,
    registry: CardPaymentStatusRegistryDep,
    settlement_registry: CardPaymentSettlementRegistryDep,
):
    settled = await settlement_registry.get(request_id)
    if settled is not None:
        return CardPaymentStatusDTO(**settled)
    resolved = await registry.get(request_id)
    if resolved is None:
        return CardPaymentStatusDTO(request_id=request_id, status="pending")
    return CardPaymentStatusDTO(**resolved)


@router.websocket("/ws/payments/{request_id}")
async def card_payment_status_socket(
    websocket: WebSocket,
    request_id: str,
    registry: CardPaymentStatusRegistryDep,
    settlement_registry: CardPaymentSettlementRegistryDep,
    settings: SettingsDep,
):
    await websocket.accept()
    try:
        resolved = await registry.wait_for(
            request_id, timeout=settings.websocket_timeout_seconds
        )
        await websocket.send_json(
            resolved or {"request_id": request_id, "status": "pending"}
        )
        # Only an approved payment ever settles (a decline never reaches
        # `CardMovementConsumer` — see `CardPaymentStatusDTO`) — waiting here
        # for any other verdict would just burn the timeout for nothing.
        if resolved is not None and resolved.get("status") == "approved":
            settled = await settlement_registry.wait_for(
                request_id, timeout=settings.websocket_timeout_seconds
            )
            if settled is not None:
                await websocket.send_json(settled)
    except (WebSocketDisconnect, RuntimeError):
        # The client went away while we were waiting. Starlette signals that
        # as a RuntimeError on send, not only as a WebSocketDisconnect.
        return
    finally:
        with suppress(RuntimeError):
            await websocket.close()
