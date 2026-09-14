"""Purchase status endpoints (Credit Cards Phase 2, design §7). Mirrors
`transfer_router.py`'s status endpoints exactly, on the purchase domain's own
`StatusRegistry` (`PurchaseStatusRegistryDep`) — never the transfer one.

Same decisions the transfer endpoints already establish, deliberately
unchanged here: an unresolved request is 200 `pending`, not 404 (the request
exists and is in flight); the WebSocket times out rather than being held open
forever.
"""
from __future__ import annotations

import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from openbankapi.api.v1.dtos.purchase_dto import PurchaseStatusDTO
from openbankapi.config.dependencies import PurchaseStatusRegistryDep, SettingsDep

LOG = logging.getLogger("openbankapi.purchase")
router = APIRouter(tags=["purchase"])


@router.get(
    "/purchases/{request_id}/status",
    response_model=PurchaseStatusDTO,
    response_model_exclude_none=True,
)
def purchase_status(request_id: str, registry: PurchaseStatusRegistryDep):
    resolved = registry.get(request_id)
    if resolved is None:
        return PurchaseStatusDTO(request_id=request_id, status="pending")
    return PurchaseStatusDTO(**resolved)


@router.websocket("/ws/purchases/{request_id}")
async def purchase_status_socket(
    websocket: WebSocket, request_id: str, registry: PurchaseStatusRegistryDep, settings: SettingsDep
):
    await websocket.accept()
    try:
        resolved = await registry.wait_for(
            request_id, timeout=settings.websocket_timeout_seconds
        )
        await websocket.send_json(
            resolved or {"request_id": request_id, "status": "pending"}
        )
    except (WebSocketDisconnect, RuntimeError):
        # The client went away while we were waiting. Starlette signals that
        # as a RuntimeError on send, not only as a WebSocketDisconnect.
        return
    finally:
        with suppress(RuntimeError):
            await websocket.close()
