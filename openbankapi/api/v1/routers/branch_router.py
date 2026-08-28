"""`branches` endpoints (spec §8.2). Soft delete: active=false."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.branch_dto import BranchCreateDTO, BranchResponseDTO, BranchUpdateDTO
from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.services.cache_aside import read_through
from openbankapi.config.dependencies import BranchRepositoryDep, BranchServiceDep, CacheDep, SettingsDep
from openbankapi.domain.exceptions import BranchNotFoundError
from openbankapi.infra.cache.interfaces import cache_key


ENTITY = "branch"
router = APIRouter(prefix="/branches", tags=["branches"])


def _dto(entity) -> dict:
    return BranchResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=BranchResponseDTO)
async def create(body: BranchCreateDTO, repository: BranchRepositoryDep):
    # A nonexistent location_id trips the FK and surfaces as
    # ReferencedEntityNotFoundError -> 422, never a raw DB error (§11.4).
    return await repository.create(
        code=body.code, name=body.name, location_id=body.location_id
    )


@router.get("", response_model=PageResponse[BranchResponseDTO])
async def list_all(repository: BranchRepositoryDep, page: PageParams = Depends()):
    result = await repository.list(limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[BranchResponseDTO.model_validate(i) for i in result.items],
        total=result.total, limit=result.limit, offset=result.offset,
    )


@router.get("/{branch_id}", response_model=BranchResponseDTO)
async def get(
    branch_id: UUID, repository: BranchRepositoryDep, cache: CacheDep, settings: SettingsDep
):
    found = await read_through(
        cache, cache_key(ENTITY, branch_id),
        lambda: repository.get(branch_id), _dto, settings.cache_ttl_seconds,
    )
    if found is None:
        raise BranchNotFoundError(branch_id)
    return found


@router.put("/{branch_id}", response_model=BranchResponseDTO)
async def update(
    branch_id: UUID, body: BranchUpdateDTO, repository: BranchRepositoryDep, cache: CacheDep
):
    updated = await repository.update(
        branch_id, code=body.code, name=body.name,
        location_id=body.location_id, active=body.active,
    )
    if updated is None:
        raise BranchNotFoundError(branch_id)
    await cache.delete(cache_key(ENTITY, branch_id))
    return updated


@router.delete("/{branch_id}", response_model=BranchResponseDTO)
async def soft_delete(branch_id: UUID, service: BranchServiceDep, cache: CacheDep):
    # The row survives: accounts reference it, and history must stay readable.
    updated = await service.deactivate(branch_id)
    if updated is None:
        raise BranchNotFoundError(branch_id)
    await cache.delete(cache_key(ENTITY, branch_id))
    return updated
