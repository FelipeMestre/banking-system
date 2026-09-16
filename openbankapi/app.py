"""FastAPI application factory.

Takes every collaborator as an argument so the whole HTTP surface can be
exercised with fakes — no broker, no Postgres, no Redis. `main.py` is the
composition root that supplies the real ones.

Everything handed in here is a process-wide singleton, stashed on
`app.state` and read back by the dependency providers in
`controllers/dependencies.py`. Request-scoped things (the DB session, and the
repositories/services built on it) are NOT arguments here at all — they are
built per request by that module's `Depends` chain, rooted in
`infra/database/session.get_db_session`.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_plugin.fast_api_client import Auth0FastAPI

from .config import Settings
from .api.v1.services import error_handlers
from .api.v1 import main as main_controller
from .infra.cache.interfaces.cache_service import ICacheService
from .infra.kafka.interfaces.event_publisher import IEventPublisher
from .infra.status_registry.interfaces.status_registry import IStatusRegistry


def create_app(
    *,
    settings: Settings,
    cache: ICacheService,
    publisher: IEventPublisher,
    sessionmaker: async_sessionmaker[AsyncSession],
    status_registry: IStatusRegistry,
    purchase_status_registry: IStatusRegistry,
    card_payment_status_registry: IStatusRegistry,
    card_payment_settlement_registry: IStatusRegistry,
    deposit_status_registry: IStatusRegistry,
    withdrawal_status_registry: IStatusRegistry,
    auth0: Optional[Auth0FastAPI] = None,
    on_start: Optional[Callable[[asyncio.AbstractEventLoop], None]] = None,
    on_stop: Optional[Callable[[], None]] = None,
    on_stop_async: Optional[Callable[[], Awaitable[None]]] = None,
    foreign_exchange_cache_service: Optional[object] = None,
) -> FastAPI:
    # All 6 registries are now always supplied by the caller (`composition.py`
    # in production, `Harness.build()` in tests) — no default-construction
    # fallback. A Redis-backed registry needs a client/domain/TTL to build,
    # so this factory cannot conjure one on its own the way the old
    # in-memory `StatusRegistry()` could.
    resolved_purchase_status_registry = purchase_status_registry
    resolved_card_payment_status_registry = card_payment_status_registry
    resolved_card_payment_settlement_registry = card_payment_settlement_registry
    resolved_deposit_status_registry = deposit_status_registry
    resolved_withdrawal_status_registry = withdrawal_status_registry

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        loop = asyncio.get_running_loop()
        status_registry.bind_loop(loop)
        resolved_purchase_status_registry.bind_loop(loop)
        resolved_card_payment_status_registry.bind_loop(loop)
        resolved_card_payment_settlement_registry.bind_loop(loop)
        resolved_deposit_status_registry.bind_loop(loop)
        resolved_withdrawal_status_registry.bind_loop(loop)
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

    app.state.settings = settings
    app.state.cache = cache
    app.state.publisher = publisher
    app.state.sessionmaker = sessionmaker
    app.state.status_registry = status_registry
    app.state.purchase_status_registry = resolved_purchase_status_registry
    app.state.card_payment_status_registry = resolved_card_payment_status_registry
    app.state.card_payment_settlement_registry = resolved_card_payment_settlement_registry
    app.state.deposit_status_registry = resolved_deposit_status_registry
    app.state.withdrawal_status_registry = resolved_withdrawal_status_registry
    app.state.auth0 = auth0
    app.state.foreign_exchange_cache_service = foreign_exchange_cache_service

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

    app.include_router(main_controller.api_router)
    return app