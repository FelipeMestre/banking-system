"""Payment endpoints (spec §8.1). Behaviour unchanged from v1.

Every decision in the v1 gateway is preserved deliberately, including the ones
that look odd:

- 202 immediately, never waiting on the ledger. This is the write path.
- An unresolved request is 200 `pending`, not 404: the request exists and is in
  flight, and 404 would read as "never heard of it".
- The WebSocket times out rather than being held open forever, so a request that
  never resolves cannot pin a connection.

The JSON stays byte-compatible with v1 so the existing frontend keeps working.
"""
from __future__ import annotations

import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from openbankapi.api.v1.dtos.transfer_dto import TransferAcceptedDTO, TransferRequestDTO, TransferStatusDTO
from openbankapi.config.dependencies import SettingsDep, StatusRegistryDep, TransferServiceDep



LOG = logging.getLogger("openbankapi.transfer")
router = APIRouter(tags=["transfer"])


@router.post("/transfer", status_code=202, response_model=TransferAcceptedDTO)
async def request_transfer(body: TransferRequestDTO, service: TransferServiceDep):
    event = await service.request_transfer(
        source_account=body.source_account,
        destination_account=body.destination_account,
        amount=body.amount,
    )
    return TransferAcceptedDTO(
        request_id=event.request_id, status="pending", fee_amount=event.fee_amount
    )


@router.get(
    "/transfer/{request_id}/status",
    response_model=TransferStatusDTO,
    response_model_exclude_none=True,
)
def transfer_status(request_id: str, registry: StatusRegistryDep):
    resolved = registry.get(request_id)
    if resolved is None:
        return TransferStatusDTO(request_id=request_id, status="pending")
    return TransferStatusDTO(**resolved)


@router.websocket("/ws/transfer/{request_id}")
async def transfer_status_socket(
    websocket: WebSocket, request_id: str, registry: StatusRegistryDep, settings: SettingsDep
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
