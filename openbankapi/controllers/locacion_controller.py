"""`locaciones` endpoints (spec §8.2). No delete: sucursales reference them."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..domain.exceptions import LocacionNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.common import PageParams, PageResponse
from .dtos.locacion_dto import LocacionCreateDTO, LocacionResponseDTO, LocacionUpdateDTO

ENTITY = "locacion"


def build_router(repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/locaciones", tags=["locaciones"])

    def _dto(entity) -> dict:
        return LocacionResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=LocacionResponseDTO)
    async def create(body: LocacionCreateDTO):
        return await repository.create(nombre=body.nombre)

    @router.get("", response_model=PageResponse[LocacionResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[LocacionResponseDTO.model_validate(i) for i in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )

    @router.get("/{locacion_id}", response_model=LocacionResponseDTO)
    async def get(locacion_id: UUID):
        found = await read_through(
            cache, cache_key(ENTITY, locacion_id),
            lambda: repository.get(locacion_id), _dto, ttl_seconds,
        )
        if found is None:
            raise LocacionNotFoundError(locacion_id)
        return found

    @router.put("/{locacion_id}", response_model=LocacionResponseDTO)
    async def update(locacion_id: UUID, body: LocacionUpdateDTO):
        updated = await repository.update(locacion_id, nombre=body.nombre)
        if updated is None:
            raise LocacionNotFoundError(locacion_id)
        await cache.delete(cache_key(ENTITY, locacion_id))
        return updated

    return router
