"""`locations` endpoints (spec §8.2). No delete: branches reference them."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..domain.exceptions import LocationNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.common import PageParams, PageResponse
from .dtos.location_dto import LocationCreateDTO, LocationResponseDTO, LocationUpdateDTO

ENTITY = "location"


def build_router(repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/locations", tags=["locations"])

    def _dto(entity) -> dict:
        return LocationResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=LocationResponseDTO)
    async def create(body: LocationCreateDTO):
        return await repository.create(name=body.name)

    @router.get("", response_model=PageResponse[LocationResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[LocationResponseDTO.model_validate(i) for i in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )

    @router.get("/{location_id}", response_model=LocationResponseDTO)
    async def get(location_id: UUID):
        found = await read_through(
            cache, cache_key(ENTITY, location_id),
            lambda: repository.get(location_id), _dto, ttl_seconds,
        )
        if found is None:
            raise LocationNotFoundError(location_id)
        return found

    @router.put("/{location_id}", response_model=LocationResponseDTO)
    async def update(location_id: UUID, body: LocationUpdateDTO):
        updated = await repository.update(location_id, name=body.name)
        if updated is None:
            raise LocationNotFoundError(location_id)
        await cache.delete(cache_key(ENTITY, location_id))
        return updated

    return router
