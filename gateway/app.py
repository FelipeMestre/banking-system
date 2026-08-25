"""FastAPI application factory (spec §6).

`create_app` takes its collaborators as arguments so the HTTP surface can be
exercised without a Kafka broker; `main.py` is the composition root that wires
in the real ones.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .models import TransferAccepted, TransferRequest, TransferStatus
from .ports import EventPublisher
from .status_registry import StatusRegistry
from .transfers import build_transfer_requested, compute_fee

LOG = logging.getLogger("gateway")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def create_app(
    settings: Settings,
    publisher: EventPublisher,
    registry: StatusRegistry,
    on_start: Optional[Callable[[asyncio.AbstractEventLoop], None]] = None,
    on_stop: Optional[Callable[[], None]] = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        registry.bind_loop(asyncio.get_running_loop())
        if on_start is not None:
            on_start(asyncio.get_running_loop())
        try:
            yield
        finally:
            if on_stop is not None:
                on_stop()

    app = FastAPI(title="Banking Payment Gateway", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/transfer", status_code=202, response_model=TransferAccepted)
    def request_transfer(request: TransferRequest):
        """Write path: one atomic append, then answer. No waiting on the ledger.

        The verdict is read back asynchronously over `GET .../status` or the
        WebSocket — that separation is the whole point of the design (§1).
        """
        request_id = str(uuid.uuid4())
        fee_amount = compute_fee(request.amount, settings.fee_flat_cents)

        event = build_transfer_requested(
            request_id=request_id,
            source_account=request.source_account,
            destination_account=request.destination_account,
            fees_account=settings.fees_account,
            amount=request.amount,
            fee_amount=fee_amount,
            now=_now(),
        )

        # Keyed by source account: that is the shard whose balance guards the
        # transfer, so the request lands in the partition that will decide it.
        publisher.publish(
            topic=settings.account_events_topic,
            key=request.source_account,
            value=event,
        )

        return TransferAccepted(request_id=request_id, status="pending", fee_amount=fee_amount)

    @app.get(
        "/transfer/{request_id}/status",
        response_model=TransferStatus,
        response_model_exclude_none=True,
    )
    def transfer_status(request_id: str):
        """Pull-style fallback for clients that would rather not hold a socket.

        An unresolved request is a normal 200 "pending", not a 404: the request
        exists and is in flight, and 404 would read as "never heard of it".
        """
        resolved = registry.get(request_id)
        if resolved is None:
            return TransferStatus(request_id=request_id, status="pending")
        return TransferStatus(**resolved)

    @app.websocket("/ws/transfer/{request_id}")
    async def transfer_status_socket(websocket: WebSocket, request_id: str):
        await websocket.accept()
        try:
            resolved = await registry.wait_for(
                request_id, timeout=settings.websocket_timeout_seconds
            )
            payload = resolved or {"request_id": request_id, "status": "pending"}
            await websocket.send_json(payload)
        except (WebSocketDisconnect, RuntimeError):
            # The client went away while we were waiting. Starlette signals that
            # as a RuntimeError on send, not only as a WebSocketDisconnect.
            return
        finally:
            with suppress(RuntimeError):
                await websocket.close()

    return app
