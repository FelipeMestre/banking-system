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
from .infra.kafka.status_registry import StatusRegistry


def create_app(
    *,
    settings: Settings,
    cache: ICacheService,
    publisher: IEventPublisher,
    sessionmaker: async_sessionmaker[AsyncSession],
    status_registry: StatusRegistry,
    purchase_status_registry: Optional[StatusRegistry] = None,
    auth0: Optional[Auth0FastAPI] = None,
    on_start: Optional[Callable[[asyncio.AbstractEventLoop], None]] = None,
    on_stop: Optional[Callable[[], None]] = None,
    on_stop_async: Optional[Callable[[], Awaitable[None]]] = None,
    foreign_exchange_cache_service: Optional[object] = None,
) -> FastAPI:
    # A separate instance from `status_registry` (transfers) by default:
    # `request_id` is only unique within its own domain's Kafka topic.
    resolved_purchase_status_registry = purchase_status_registry or StatusRegistry()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        loop = asyncio.get_running_loop()
        status_registry.bind_loop(loop)
        resolved_purchase_status_registry.bind_loop(loop)
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