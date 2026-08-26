"""Builds the real app with fake ports — no broker, no Postgres, no Redis."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from openbankapi.app import create_app
from openbankapi.config import Settings
from openbankapi.domain.service import CuentaService, TransferenciaService
from openbankapi.infra.kafka.services import StatusRegistry

from .fakes import (
    FakeClienteRepository,
    FakeCuentaRepository,
    FakeLocacionRepository,
    FakePublisher,
    FakeSucursalRepository,
    FakeCache,
)


class Harness:
    def __init__(self, client, publisher, cache, registry, repos, settings):
        self.client = client
        self.publisher = publisher
        self.cache = cache
        self.registry = registry
        self.locaciones, self.sucursales, self.clientes, self.cuentas = repos
        self.settings = settings


def build(*, cache=None, cuentas=None, sucursales=None) -> Harness:
    settings = Settings(fee_flat_cents=25, websocket_timeout_seconds=0.2, cache_ttl_seconds=300)
    publisher = FakePublisher()
    cache = cache or FakeCache()
    registry = StatusRegistry()

    locaciones = FakeLocacionRepository()
    sucursales = sucursales or FakeSucursalRepository()
    clientes = FakeClienteRepository()
    cuentas = cuentas or FakeCuentaRepository()

    app = create_app(
        settings=settings,
        transfer_service=TransferenciaService(settings, publisher),
        cuenta_service=CuentaService(settings, cuentas, publisher),
        status_registry=registry,
        locacion_repository=locaciones,
        sucursal_repository=sucursales,
        cliente_repository=clientes,
        cuenta_repository=cuentas,
        cache=cache,
    )
    client = TestClient(app)
    return Harness(client, publisher, cache, registry,
                   (locaciones, sucursales, clientes, cuentas), settings)


@pytest.fixture
def harness():
    h = build()
    with h.client:
        yield h


@pytest.fixture
def wired():
    """A harness whose reference data already exists, ready for account work."""
    cliente_id, sucursal_id = uuid.uuid4(), uuid.uuid4()
    cuentas = FakeCuentaRepository(known_clientes={cliente_id}, known_sucursales={sucursal_id})
    h = build(cuentas=cuentas)
    h.cliente_id, h.sucursal_id = cliente_id, sucursal_id
    with h.client:
        yield h
