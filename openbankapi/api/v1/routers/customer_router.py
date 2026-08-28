"""`customers` endpoints (spec §8.2). Soft delete: active=false.

Nothing in this module logs `date_of_birth` or `gender` (spec §3.4).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.dtos.customer_dto import CustomerCreateDTO, CustomerResponseDTO, CustomerUpdateDTO
from openbankapi.api.v1.services.cache_aside import read_through
from openbankapi.config.dependencies import CacheDep, CustomerRepositoryDep, CustomerServiceDep, SettingsDep
from openbankapi.domain.exceptions import CustomerNotFoundError
from openbankapi.infra.cache.interfaces import cache_key



ENTITY = "customer"
router = APIRouter(prefix="/customers", tags=["customers"])


def _dto(entity) -> dict:
    return CustomerResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=CustomerResponseDTO)
async def create(body: CustomerCreateDTO, repository: CustomerRepositoryDep):
    return await repository.create(
        identification_number=body.identification_number,
        first_name=body.first_name, last_name=body.last_name,
        date_of_birth=body.date_of_birth, gender=body.gender,
    )


@router.get("", response_model=PageResponse[CustomerResponseDTO])
async def list_all(repository: CustomerRepositoryDep, page: PageParams = Depends()):
    result = await repository.list(limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[CustomerResponseDTO.model_validate(i) for i in result.items],
        total=result.total, limit=result.limit, offset=result.offset,
    )


@router.get("/{customer_id}", response_model=CustomerResponseDTO)
async def get(
    customer_id: UUID, repository: CustomerRepositoryDep, cache: CacheDep, settings: SettingsDep
):
    found = await read_through(
        cache, cache_key(ENTITY, customer_id),
        lambda: repository.get(customer_id), _dto, settings.cache_ttl_seconds,
    )
    if found is None:
        raise CustomerNotFoundError(customer_id)
    return found


@router.put("/{customer_id}", response_model=CustomerResponseDTO)
async def update(
    customer_id: UUID,
    body: CustomerUpdateDTO,
    repository: CustomerRepositoryDep,
    cache: CacheDep,
):
    updated = await repository.update(
        customer_id,
        identification_number=body.identification_number,
        first_name=body.first_name, last_name=body.last_name,
        date_of_birth=body.date_of_birth, gender=body.gender,
        active=body.active,
    )
    if updated is None:
        raise CustomerNotFoundError(customer_id)
    await cache.delete(cache_key(ENTITY, customer_id))
    return updated


@router.delete("/{customer_id}", response_model=CustomerResponseDTO)
async def soft_delete(customer_id: UUID, service: CustomerServiceDep, cache: CacheDep):
    updated = await service.deactivate(customer_id)
    if updated is None:
        raise CustomerNotFoundError(customer_id)
    await cache.delete(cache_key(ENTITY, customer_id))
    return updated
