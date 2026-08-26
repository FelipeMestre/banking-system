"""In-memory doubles for every outbound port.

The whole API surface is exercised without a broker, a database or Redis. That
is only possible because every dependency is a port; if a controller reached for
asyncpg directly none of this would work.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from openbankapi.domain.exceptions import (
    DuplicateAccountNumberError,
    DuplicateError,
    ReferencedEntityNotFoundError,
)
from openbankapi.domain.model import Cliente, Cuenta, EstadoCuenta, Locacion, Sucursal
from openbankapi.infra.database.interfaces.common import Page


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class FakePublisher:
    def __init__(self):
        self.published: List[tuple] = []

    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        self.published.append((topic, key, value))


class FakeCache:
    """Counts hits and misses so cache-aside can actually be asserted."""

    def __init__(self, *, failing: bool = False):
        self.store: Dict[str, Any] = {}
        self.failing = failing
        self.gets = 0
        self.deletes: List[str] = []

    async def get(self, key: str):
        self.gets += 1
        if self.failing:
            return None  # a broken cache degrades to a miss, never an error
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        if not self.failing:
            self.store[key] = value

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.store.pop(key, None)

    async def close(self) -> None:
        return None


class FakeLocacionRepository:
    def __init__(self):
        self.rows: Dict[UUID, Locacion] = {}
        self.loads = 0

    async def create(self, *, nombre: str) -> Locacion:
        entity = Locacion(id=uuid.uuid4(), nombre=nombre, created_at=_now(), updated_at=_now())
        self.rows[entity.id] = entity
        return entity

    async def get(self, locacion_id: UUID) -> Optional[Locacion]:
        self.loads += 1
        return self.rows.get(locacion_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, locacion_id: UUID, *, nombre: Optional[str]) -> Optional[Locacion]:
        current = self.rows.get(locacion_id)
        if current is None:
            return None
        updated = Locacion(id=current.id, nombre=nombre or current.nombre,
                           created_at=current.created_at, updated_at=_now())
        self.rows[locacion_id] = updated
        return updated


class FakeSucursalRepository:
    def __init__(self, *, known_locaciones: Optional[set] = None):
        self.rows: Dict[UUID, Sucursal] = {}
        self.known_locaciones = known_locaciones if known_locaciones is not None else set()
        self.codigos: set = set()

    async def create(self, *, codigo: str, nombre: str, locacion_id: UUID) -> Sucursal:
        # Stands in for the FK: the real repository lets Postgres decide and
        # translates the violation, but the domain error is the same.
        if locacion_id not in self.known_locaciones:
            raise ReferencedEntityNotFoundError("locacion_id", locacion_id)
        if codigo in self.codigos:
            raise DuplicateError("codigo", codigo)
        self.codigos.add(codigo)
        entity = Sucursal(id=uuid.uuid4(), codigo=codigo, nombre=nombre,
                          locacion_id=locacion_id, activa=True,
                          created_at=_now(), updated_at=_now())
        self.rows[entity.id] = entity
        return entity

    async def get(self, sucursal_id: UUID) -> Optional[Sucursal]:
        return self.rows.get(sucursal_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, sucursal_id: UUID, **changes) -> Optional[Sucursal]:
        current = self.rows.get(sucursal_id)
        if current is None:
            return None
        updated = Sucursal(
            id=current.id,
            codigo=changes.get("codigo") or current.codigo,
            nombre=changes.get("nombre") or current.nombre,
            locacion_id=changes.get("locacion_id") or current.locacion_id,
            activa=current.activa if changes.get("activa") is None else changes["activa"],
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[sucursal_id] = updated
        return updated

    async def deactivate(self, sucursal_id: UUID) -> Optional[Sucursal]:
        return await self.update(sucursal_id, activa=False)


class FakeClienteRepository:
    def __init__(self):
        self.rows: Dict[UUID, Cliente] = {}

    async def create(self, **kwargs) -> Cliente:
        entity = Cliente(id=uuid.uuid4(), activo=True, created_at=_now(),
                         updated_at=_now(), **kwargs)
        self.rows[entity.id] = entity
        return entity

    async def get(self, cliente_id: UUID) -> Optional[Cliente]:
        return self.rows.get(cliente_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, cliente_id: UUID, **changes) -> Optional[Cliente]:
        current = self.rows.get(cliente_id)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Cliente(
            id=current.id,
            numero_identificacion=supplied.get("numero_identificacion", current.numero_identificacion),
            nombre=supplied.get("nombre", current.nombre),
            apellido=supplied.get("apellido", current.apellido),
            fecha_nacimiento=supplied.get("fecha_nacimiento", current.fecha_nacimiento),
            genero=supplied.get("genero", current.genero),
            activo=supplied.get("activo", current.activo),
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[cliente_id] = updated
        return updated

    async def deactivate(self, cliente_id: UUID) -> Optional[Cliente]:
        return await self.update(cliente_id, activo=False)


class FakeCuentaRepository:
    """Also plays the balance projection, so a test can watch both sides."""

    def __init__(self, *, known_clientes=None, known_sucursales=None, collide_times: int = 0):
        self.rows: Dict[str, Cuenta] = {}
        self.known_clientes = known_clientes if known_clientes is not None else set()
        self.known_sucursales = known_sucursales if known_sucursales is not None else set()
        self.collide_times = collide_times
        self.attempts = 0

    async def create(self, *, moneda: str, cliente_id: UUID, sucursal_id: UUID) -> Cuenta:
        if cliente_id not in self.known_clientes:
            raise ReferencedEntityNotFoundError("cliente_id", cliente_id)
        if sucursal_id not in self.known_sucursales:
            raise ReferencedEntityNotFoundError("sucursal_id", sucursal_id)
        from openbankapi.infra.database.repositories import generate_numero_cuenta

        for _ in range(5):
            self.attempts += 1
            numero = generate_numero_cuenta()
            if self.collide_times > 0:
                self.collide_times -= 1
                continue  # simulate the UNIQUE violation the real repo retries
            entity = Cuenta(id=uuid.uuid4(), numero_cuenta=numero, moneda=moneda,
                            cliente_id=cliente_id, sucursal_id=sucursal_id, saldo=0,
                            estado=EstadoCuenta.ACTIVA, created_at=_now(), updated_at=_now())
            self.rows[numero] = entity
            return entity
        raise DuplicateAccountNumberError("exhausted")

    async def get_by_numero(self, numero_cuenta: str) -> Optional[Cuenta]:
        return self.rows.get(numero_cuenta)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, numero_cuenta: str, **changes) -> Optional[Cuenta]:
        assert "saldo" not in changes, "saldo must never reach the repository"
        current = self.rows.get(numero_cuenta)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Cuenta(
            id=current.id, numero_cuenta=current.numero_cuenta,
            moneda=supplied.get("moneda", current.moneda),
            cliente_id=current.cliente_id,
            sucursal_id=supplied.get("sucursal_id", current.sucursal_id),
            saldo=current.saldo,  # never from the caller
            estado=EstadoCuenta(supplied.get("estado", current.estado.value)),
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[numero_cuenta] = updated
        return updated

    async def close(self, numero_cuenta: str) -> Optional[Cuenta]:
        return await self.update(numero_cuenta, estado="cerrada")

    async def apply_balance(self, numero_cuenta: str, balance: int) -> bool:
        current = self.rows.get(numero_cuenta)
        if current is None:
            return False
        self.rows[numero_cuenta] = Cuenta(
            id=current.id, numero_cuenta=current.numero_cuenta, moneda=current.moneda,
            cliente_id=current.cliente_id, sucursal_id=current.sucursal_id,
            saldo=balance, estado=current.estado,
            created_at=current.created_at, updated_at=_now(),
        )
        return True
