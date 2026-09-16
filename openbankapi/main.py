"""HTTP composition root (spec §7.2 + worker-http-split).

Owns only the FastAPI app and Auth0 wiring. Every collaborator both this
process and `worker.py` need comes from `composition.py`. `openbankapi`
never starts a Kafka consumer here (worker-http-split requirement) — the 6
status registries are read/written straight through Redis, never bound to a
consumer-fed thread in this process. `publisher` IS still used here though:
HTTP routes (transfer/deposit/withdrawal) publish request events onto Kafka,
they just never consume from it.
"""

from __future__ import annotations

from fastapi_plugin.fast_api_client import Auth0FastAPI

from . import composition
from .app import create_app

# None until AUTH0_DOMAIN/AUTH0_AUDIENCE are set (an Auth0 "API" resource has
# to exist first — see config/dependencies.py for how routes degrade to a
# clear 503 instead of crashing the whole app when this is unset).
auth0 = (
    Auth0FastAPI(domain=composition.settings.auth0_domain, audience=composition.settings.auth0_audience)
    if composition.settings.auth0_domain and composition.settings.auth0_audience
    else None
)


def _stop() -> None:
    composition.publisher.close()


async def _stop_async() -> None:
    await composition.cache.close()
    await composition.close_status_registry_client()
    await composition.engine.dispose()


app = create_app(
    settings=composition.settings,
    cache=composition.cache,
    publisher=composition.publisher,
    sessionmaker=composition.sessionmaker,
    status_registry=composition.status_registry,
    purchase_status_registry=composition.purchase_status_registry,
    card_payment_status_registry=composition.card_payment_status_registry,
    card_payment_settlement_registry=composition.card_payment_settlement_registry,
    deposit_status_registry=composition.deposit_status_registry,
    withdrawal_status_registry=composition.withdrawal_status_registry,
    auth0=auth0,
    on_stop=_stop,
    on_stop_async=_stop_async,
    foreign_exchange_cache_service=composition.foreign_exchange_cache_service,
)
