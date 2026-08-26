"""`customers` endpoints (spec §8.2). Soft delete: active=false.

Nothing in this module logs `date_of_birth` or `gender` (spec §3.4).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from ..domain.exceptions import CustomerNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.customer_dto import CustomerCreateDTO, CustomerResponseDTO, CustomerUpdateDTO
from .dtos.common import PageParams, PageResponse

ENTITY = "customer"


def build_router(repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/customers", tags=["customers"])

    def _dto(entity) -> dict:
        return CustomerResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=CustomerResponseDTO)
    async def create(body: CustomerCreateDTO):
        return await repository.create(
            identification_number=body.identification_number,
            first_name=body.first_name, last_name=body.last_name,
            date_of_birth=body.date_of_birth, gender=body.gender,
        )

    @router.get("", response_model=PageResponse[CustomerResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[CustomerResponseDTO.model_validate(i) for i in result.items],
            total=result.total, limit=result.limit, offset=result.offset,
        )

    @router.get("/{customer_id}", response_model=CustomerResponseDTO)
    async def get(customer_id: UUID):
        found = await read_through(
            cache, cache_key(ENTITY, customer_id),
            lambda: repository.get(customer_id), _dto, ttl_seconds,
        )
        if found is None:
            raise CustomerNotFoundError(customer_id)
        return found

    @router.put("/{customer_id}", response_model=CustomerResponseDTO)
    async def update(customer_id: UUID, body: CustomerUpdateDTO):
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
    async def soft_delete(customer_id: UUID):
        updated = await repository.deactivate(customer_id)
        if updated is None:
            raise CustomerNotFoundError(customer_id)
        await cache.delete(cache_key(ENTITY, customer_id))
        return updated

    return router
