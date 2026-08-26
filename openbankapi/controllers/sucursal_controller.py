"""`sucursales` endpoints (spec §8.2). Soft delete: activa=false."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from ..domain.exceptions import SucursalNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.common import PageParams, PageResponse
from .dtos.sucursal_dto import SucursalCreateDTO, SucursalResponseDTO, SucursalUpdateDTO

ENTITY = "sucursal"


def build_router(repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/sucursales", tags=["sucursales"])

    def _dto(entity) -> dict:
        return SucursalResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=SucursalResponseDTO)
    async def create(body: SucursalCreateDTO):
        # A nonexistent locacion_id trips the FK and surfaces as
        # ReferencedEntityNotFoundError -> 422, never a raw DB error (§11.4).
        return await repository.create(
            codigo=body.codigo, nombre=body.nombre, locacion_id=body.locacion_id
        )

    @router.get("", response_model=PageResponse[SucursalResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[SucursalResponseDTO.model_validate(i) for i in result.items],
            total=result.total, limit=result.limit, offset=result.offset,
        )

    @router.get("/{sucursal_id}", response_model=SucursalResponseDTO)
    async def get(sucursal_id: UUID):
        found = await read_through(
            cache, cache_key(ENTITY, sucursal_id),
            lambda: repository.get(sucursal_id), _dto, ttl_seconds,
        )
        if found is None:
            raise SucursalNotFoundError(sucursal_id)
        return found

    @router.put("/{sucursal_id}", response_model=SucursalResponseDTO)
    async def update(sucursal_id: UUID, body: SucursalUpdateDTO):
        updated = await repository.update(
            sucursal_id, codigo=body.codigo, nombre=body.nombre,
            locacion_id=body.locacion_id, activa=body.activa,
        )
        if updated is None:
            raise SucursalNotFoundError(sucursal_id)
        await cache.delete(cache_key(ENTITY, sucursal_id))
        return updated

    @router.delete("/{sucursal_id}", response_model=SucursalResponseDTO)
    async def soft_delete(sucursal_id: UUID):
        # The row survives: accounts reference it, and history must stay readable.
        updated = await repository.deactivate(sucursal_id)
        if updated is None:
            raise SucursalNotFoundError(sucursal_id)
        await cache.delete(cache_key(ENTITY, sucursal_id))
        return updated

    return router
