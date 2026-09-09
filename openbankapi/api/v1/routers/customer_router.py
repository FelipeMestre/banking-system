"""`customers` endpoints (spec §8.2). Soft delete: active=false.

Nothing in this module logs `date_of_birth` or `gender` (spec §3.4).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.dtos.customer_dto import (
    CustomerAuth0LinkDTO,
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerUpdateDTO,
)
from openbankapi.api.v1.services.cache_aside import read_through
from typing import Annotated

from openbankapi.config.dependencies import (
    CacheDep,
    CurrentCustomerDep,
    CurrentUserDep,
    CustomerRepositoryDep,
    CustomerServiceDep,
    SettingsDep,
    require_permissions,
)
from openbankapi.domain.exceptions import CustomerNotFoundError
from openbankapi.infra.cache.interfaces import cache_key

ReadAdminDep = Annotated[dict, Depends(require_permissions("read:admin"))]
WriteAdminDep = Annotated[dict, Depends(require_permissions("write:admin"))]



ENTITY = "customer"
router = APIRouter(prefix="/customers", tags=["customers"])


def _dto(entity) -> dict:
    return CustomerResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=CustomerResponseDTO)
async def create(body: CustomerCreateDTO, repository: CustomerRepositoryDep, _claims: WriteAdminDep):
    return await repository.create(
        identification_number=body.identification_number,
        first_name=body.first_name, last_name=body.last_name,
        date_of_birth=body.date_of_birth, gender=body.gender,
    )


@router.get("", response_model=PageResponse[CustomerResponseDTO])
async def list_all(
    _claims: ReadAdminDep, repository: CustomerRepositoryDep, page: PageParams = Depends()
):
    result = await repository.list(limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[CustomerResponseDTO.model_validate(i) for i in result.items],
        total=result.total, limit=result.limit, offset=result.offset,
    )


@router.get("/me", response_model=CustomerResponseDTO)
async def get_me(customer: CurrentCustomerDep):
    """The Customer linked to the caller's Auth0 identity (spec §1.2).

    Declared before `/{customer_id}` on purpose: FastAPI matches routes in
    declaration order, and `me` would otherwise be swallowed as a (invalid)
    UUID path parameter.
    """
    return _dto(customer)


@router.patch("/{customer_id}/auth0-link", response_model=CustomerResponseDTO)
async def link_auth0(
    customer_id: UUID, body: CustomerAuth0LinkDTO, repository: CustomerRepositoryDep, cache: CacheDep, _claims: WriteAdminDep
):
    """Link a Customer to an Auth0 identity (spec §1.3). Now requires write:admin."""
    updated = await repository.update(customer_id, auth0_sub=body.sub)
    if updated is None:
        raise CustomerNotFoundError(customer_id)
    await cache.delete(cache_key(ENTITY, customer_id))
    return updated


@router.get("/{customer_id}", response_model=CustomerResponseDTO)
async def get(
    customer_id: UUID,
    repository: CustomerRepositoryDep,
    cache: CacheDep,
    settings: SettingsDep,
    _claims: ReadAdminDep,
):
    """Requires read:admin (spec). Previously CurrentUserDep, now admin read."""
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
    _claims: WriteAdminDep,
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
async def soft_delete(customer_id: UUID, service: CustomerServiceDep, cache: CacheDep, _claims: WriteAdminDep):
    updated = await service.deactivate(customer_id)
    if updated is None:
        raise CustomerNotFoundError(customer_id)
    await cache.delete(cache_key(ENTITY, customer_id))
    return updated
