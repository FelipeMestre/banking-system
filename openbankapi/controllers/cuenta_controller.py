"""`cuentas` endpoints (spec §8.2).

The update route can NEVER change a balance. `CuentaUpdateDTO` has no `saldo`
field and `extra="forbid"` rejects one that is sent anyway (spec §11.3); beyond
that, this controller is handed an `ICuentaRepository`, which has no method that
writes `saldo` at all. Two independent structural guards, neither of them a
validator that someone could later relax.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..domain.exceptions import CuentaNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.common import PageParams, PageResponse
from .dtos.cuenta_dto import CuentaCreateDTO, CuentaResponseDTO, CuentaUpdateDTO

ENTITY = "cuenta"


def build_router(service, repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/cuentas", tags=["cuentas"])

    def _dto(entity) -> dict:
        return CuentaResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=CuentaResponseDTO)
    async def create(body: CuentaCreateDTO):
        """`numero_cuenta` is generated server-side: it is the Kafka partition
        key, so it must be correct by construction (spec §8.2). A collision on
        the generated value is retried internally and never becomes a 500."""
        return await service.open_account(
            moneda=body.moneda, cliente_id=body.cliente_id, sucursal_id=body.sucursal_id
        )

    @router.get("", response_model=PageResponse[CuentaResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[CuentaResponseDTO.model_validate(i) for i in result.items],
            total=result.total, limit=result.limit, offset=result.offset,
        )

    @router.get("/{numero_cuenta}", response_model=CuentaResponseDTO)
    async def get(numero_cuenta: str):
        """`saldo` here is eventually consistent (spec §3.6): it lags the ledger
        by however long the account-balances consumer takes, typically a few
        hundred milliseconds. Stale is acceptable; wrong is not."""
        found = await read_through(
            cache, cache_key(ENTITY, numero_cuenta),
            lambda: repository.get_by_numero(numero_cuenta), _dto, ttl_seconds,
        )
        if found is None:
            raise CuentaNotFoundError(numero_cuenta)
        return found

    @router.put("/{numero_cuenta}", response_model=CuentaResponseDTO)
    async def update(numero_cuenta: str, body: CuentaUpdateDTO):
        updated = await repository.update(
            numero_cuenta, moneda=body.moneda,
            sucursal_id=body.sucursal_id, estado=body.estado,
        )
        if updated is None:
            raise CuentaNotFoundError(numero_cuenta)
        await cache.delete(cache_key(ENTITY, numero_cuenta))
        return updated

    @router.delete("/{numero_cuenta}", response_model=CuentaResponseDTO)
    async def soft_delete(numero_cuenta: str):
        updated = await repository.close(numero_cuenta)
        if updated is None:
            raise CuentaNotFoundError(numero_cuenta)
        await cache.delete(cache_key(ENTITY, numero_cuenta))
        return updated

    return router
