"""FastAPI application factory.

Takes every collaborator as an argument so the whole HTTP surface can be
exercised with fakes — no broker, no Postgres, no Redis. `main.py` is the
composition root that supplies the real ones.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .controllers import (
    customer_controller,
    account_controller,
    error_handlers,
    location_controller,
    branch_controller,
    transfer_controller,
)


def create_app(
    *,
    settings: Settings,
    transfer_service,
    account_service,
    status_registry,
    location_repository,
    branch_repository,
    customer_repository,
    account_repository,
    cache,
    on_start: Optional[Callable[[asyncio.AbstractEventLoop], None]] = None,
    on_stop: Optional[Callable[[], None]] = None,
    on_stop_async: Optional[Callable[[], Awaitable[None]]] = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        loop = asyncio.get_running_loop()
        status_registry.bind_loop(loop)
        if on_start is not None:
            on_start(loop)
        try:
            yield
        finally:
            # Consumers stop first: they hand work to the loop, so tearing the
            # database down underneath a running one would fail its last writes.
            if on_stop is not None:
                on_stop()
            if on_stop_async is not None:
                await on_stop_async()

    app = FastAPI(title="OpenBankAPI", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    error_handlers.install(app)

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    ttl = settings.cache_ttl_seconds
    app.include_router(
        transfer_controller.build_router(
            transfer_service, status_registry, settings.websocket_timeout_seconds
        )
    )
    app.include_router(location_controller.build_router(location_repository, cache, ttl))
    app.include_router(branch_controller.build_router(branch_repository, cache, ttl))
    app.include_router(customer_controller.build_router(customer_repository, cache, ttl))
    app.include_router(
        account_controller.build_router(account_service, account_repository, cache, ttl)
    )
    return app
