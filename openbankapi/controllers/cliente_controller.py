"""`clientes` endpoints (spec §8.2). Soft delete: activo=false.

Nothing in this module logs `fecha_nacimiento` or `genero` (spec §3.4).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from ..domain.exceptions import ClienteNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.cliente_dto import ClienteCreateDTO, ClienteResponseDTO, ClienteUpdateDTO
from .dtos.common import PageParams, PageResponse

ENTITY = "cliente"


def build_router(repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/clientes", tags=["clientes"])

    def _dto(entity) -> dict:
        return ClienteResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=ClienteResponseDTO)
    async def create(body: ClienteCreateDTO):
        return await repository.create(
            numero_identificacion=body.numero_identificacion,
            nombre=body.nombre, apellido=body.apellido,
            fecha_nacimiento=body.fecha_nacimiento, genero=body.genero,
        )

    @router.get("", response_model=PageResponse[ClienteResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[ClienteResponseDTO.model_validate(i) for i in result.items],
            total=result.total, limit=result.limit, offset=result.offset,
        )

    @router.get("/{cliente_id}", response_model=ClienteResponseDTO)
    async def get(cliente_id: UUID):
        found = await read_through(
            cache, cache_key(ENTITY, cliente_id),
            lambda: repository.get(cliente_id), _dto, ttl_seconds,
        )
        if found is None:
            raise ClienteNotFoundError(cliente_id)
        return found

    @router.put("/{cliente_id}", response_model=ClienteResponseDTO)
    async def update(cliente_id: UUID, body: ClienteUpdateDTO):
        updated = await repository.update(
            cliente_id,
            numero_identificacion=body.numero_identificacion,
            nombre=body.nombre, apellido=body.apellido,
            fecha_nacimiento=body.fecha_nacimiento, genero=body.genero,
            activo=body.activo,
        )
        if updated is None:
            raise ClienteNotFoundError(cliente_id)
        await cache.delete(cache_key(ENTITY, cliente_id))
        return updated

    @router.delete("/{cliente_id}", response_model=ClienteResponseDTO)
    async def soft_delete(cliente_id: UUID):
        updated = await repository.deactivate(cliente_id)
        if updated is None:
            raise ClienteNotFoundError(cliente_id)
        await cache.delete(cache_key(ENTITY, cliente_id))
        return updated

    return router
