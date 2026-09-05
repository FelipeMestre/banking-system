"""`locations` endpoints (spec §8.2). Soft delete: active=false."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from typing import Annotated

from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.dtos.location_dto import LocationCreateDTO, LocationResponseDTO, LocationUpdateDTO
from openbankapi.api.v1.services.cache_aside import read_through
from openbankapi.config.dependencies import (
    CacheDep,
    LocationRepositoryDep,
    SettingsDep,
    require_permissions,
)
from openbankapi.domain.exceptions import LocationNotFoundError
from openbankapi.infra.cache.interfaces import cache_key

ReadAdminDep = Annotated[dict, Depends(require_permissions("read:admin"))]
WriteAdminDep = Annotated[dict, Depends(require_permissions("write:admin"))]



ENTITY = "location"
router = APIRouter(prefix="/locations", tags=["locations"])


def _dto(entity) -> dict:
    return LocationResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=LocationResponseDTO)
async def create(body: LocationCreateDTO, repository: LocationRepositoryDep, _claims: WriteAdminDep):
    return await repository.create(name=body.name)


@router.get("", response_model=PageResponse[LocationResponseDTO])
async def list_all(
    _claims: ReadAdminDep, repository: LocationRepositoryDep, page: PageParams = Depends()
):
    result = await repository.list(limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[LocationResponseDTO.model_validate(i) for i in result.items],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.get("/{location_id}", response_model=LocationResponseDTO)
async def get(
    location_id: UUID, repository: LocationRepositoryDep, cache: CacheDep, settings: SettingsDep, _claims: ReadAdminDep
):
    found = await read_through(
        cache, cache_key(ENTITY, location_id),
        lambda: repository.get(location_id), _dto, settings.cache_ttl_seconds,
    )
    if found is None:
        raise LocationNotFoundError(location_id)
    return found


@router.put("/{location_id}", response_model=LocationResponseDTO)
async def update(
    location_id: UUID,
    body: LocationUpdateDTO,
    repository: LocationRepositoryDep,
    cache: CacheDep,
    _claims: WriteAdminDep,
):
    updated = await repository.update(location_id, name=body.name, active=body.active)
    if updated is None:
        raise LocationNotFoundError(location_id)
    await cache.delete(cache_key(ENTITY, location_id))
    return updated


@router.delete("/{location_id}", response_model=LocationResponseDTO)
async def soft_delete(location_id: UUID, repository: LocationRepositoryDep, cache: CacheDep, _claims: WriteAdminDep):
    # The row survives: branches reference it, and history must stay readable.
    updated = await repository.deactivate(location_id)
    if updated is None:
        raise LocationNotFoundError(location_id)
    await cache.delete(cache_key(ENTITY, location_id))
    return updated
