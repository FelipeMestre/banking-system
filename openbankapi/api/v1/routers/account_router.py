"""`accounts` endpoints (spec §8.2).

The update route can NEVER change a balance. `AccountUpdateDTO` has no `balance`
field and `extra="forbid"` rejects one that is sent anyway (spec §11.3); beyond
that, this controller is handed an `IAccountRepository`, which has no method that
writes `balance` at all. Two independent structural guards, neither of them a
validator that someone could later relax.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from openbankapi.api.v1.dtos.account_dto import AccountCreateDTO, AccountResponseDTO, AccountUpdateDTO
from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.dtos.first_account_dto import FirstAccountCreateDTO, FirstAccountKycDTO
from openbankapi.api.v1.dtos.transaction_dto import TransactionsPageDTO, TransactionsPageParams
from openbankapi.api.v1.services.cache_aside import read_through
from typing import Annotated

from openbankapi.config.dependencies import (
    AccountRepositoryDep,
    AccountServiceDep,
    CacheDep,
    CurrentCustomerDep,
    CurrentUserDep,
    CustomerRepositoryDep,
    SettingsDep,
    TransactionServiceDep,
    require_permissions,
)
from openbankapi.domain.exceptions import AccountAccessForbiddenError, AccountNotFoundError
from openbankapi.infra.cache.interfaces import cache_key

ReadAdminDep = Annotated[dict, Depends(require_permissions("read:admin"))]
WriteAdminDep = Annotated[dict, Depends(require_permissions("write:admin"))]

ENTITY = "account"
router = APIRouter(prefix="/accounts", tags=["accounts"])


def _dto(entity) -> dict:
    return AccountResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=AccountResponseDTO)
async def create(body: AccountCreateDTO, service: AccountServiceDep, _claims: WriteAdminDep):
    """`account_number` is generated server-side: it is the Kafka partition
    key, so it must be correct by construction (spec §8.2). A collision on
    the generated value is retried internally and never becomes a 500."""
    return await service.open_account(
        currency=body.currency, customer_id=body.customer_id, branch_id=body.branch_id
    )


@router.post("/me", status_code=201, response_model=AccountResponseDTO)
async def create_first_account(
    claims: CurrentUserDep,
    service: AccountServiceDep,
    customer_repository: CustomerRepositoryDep,
    body: FirstAccountCreateDTO = FirstAccountCreateDTO(),
):
    """Self-service first account (spec: zero client-supplied account params).

    `currency`/`branch_id` in a client-sent body are always ignored, never
    read — currency is always USD and the branch is always the
    server-resolved oldest active branch (see `open_first_account`).

    Runs under `CurrentUserDep` (raw claims), not `CurrentCustomerDep`, so an
    identity with no linked `Customer` reaches this body instead of 404ing
    before it runs (amendment). The lookup happens here so the two cases can
    branch:

    - Already linked: the KYC body, if any, is read but never passed to any
      repository call — it is discarded entirely, so an existing Customer's
      data can never be overwritten by a body sent along for the ride (spec —
      "Linked customer, KYC body ignored").
    - Never linked: the KYC fields are re-validated against the strict
      `FirstAccountKycDTO` (422 on missing/invalid, including under-18) before
      `AccountService.open_first_account_for_identity` ever runs — keeping
      that validation in the router, not the domain service, so the domain
      layer never imports a DTO or Pydantic (this codebase's layering rule).

    Concurrency note: the atomic lock-then-check-then-insert ordering that
    keeps two concurrent requests for the same identity from both succeeding
    is implemented in `AccountService` via `pg_advisory_xact_lock`. It is
    verified by code review and manual/staging testing, not by this
    single-threaded fake-backed suite (see design's Testing Strategy —
    Atomicity / Concurrency rows).
    """
    sub = claims.get("sub", "")
    customer = await customer_repository.get_by_auth0_sub(sub)
    if customer is not None:
        return await service.open_first_account(customer)

    try:
        kyc = FirstAccountKycDTO.model_validate(body.model_dump())
    except ValidationError as error:
        # `include_context=False`: a `ctx` entry can carry the raw exception
        # object a `@field_validator` raised (e.g. the underage `ValueError`
        # below) — not JSON-serializable, and error_handlers.py's own
        # `RequestValidationError` handler only strips `input`, not `ctx`.
        raise RequestValidationError(error.errors(include_url=False, include_context=False)) from error

    return await service.open_first_account_for_identity(
        sub,
        identification_number=kyc.identification_number,
        first_name=kyc.first_name,
        last_name=kyc.last_name,
        date_of_birth=kyc.date_of_birth,
        gender=kyc.gender,
    )


@router.get("", response_model=PageResponse[AccountResponseDTO])
async def list_all(
    _claims: ReadAdminDep,
    repository: AccountRepositoryDep,
    customer: CurrentCustomerDep,
    page: PageParams = Depends(),
):
    """Admin list — requires read:admin on top of customer scoping."""
    result = await repository.list_by_customer(customer.id, limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[AccountResponseDTO.model_validate(i) for i in result.items],
        total=result.total, limit=result.limit, offset=result.offset,
    )


@router.get("/{account_number}/transactions", response_model=TransactionsPageDTO)
async def list_transactions(
    _claims: ReadAdminDep,
    account_number: str,
    repository: AccountRepositoryDep,
    customer: CurrentCustomerDep,
    service: TransactionServiceDep,
    page: TransactionsPageParams = Depends(),
):
    """Requires read:admin plus ownership check."""
    account = await repository.get_by_account_number(account_number)
    if account is None:
        raise AccountNotFoundError(account_number)
    if account.customer_id != customer.id:
        raise AccountAccessForbiddenError(account_number)
    result = await service.list_for_account(account_number, limit=page.limit, cursor=page.cursor)
    return TransactionsPageDTO(items=result.items, next_cursor=result.next_cursor)


@router.get("/{account_number}", response_model=AccountResponseDTO)
async def get(
    account_number: str,
    repository: AccountRepositoryDep,
    cache: CacheDep,
    settings: SettingsDep,
    _claims: ReadAdminDep,
):
    """Requires read:admin (admin preview)."""
    found = await read_through(
        cache, cache_key(ENTITY, account_number),
        lambda: repository.get_by_account_number(account_number), _dto, settings.cache_ttl_seconds,
    )
    if found is None:
        raise AccountNotFoundError(account_number)
    return found


@router.put("/{account_number}", response_model=AccountResponseDTO)
async def update(
    account_number: str,
    body: AccountUpdateDTO,
    repository: AccountRepositoryDep,
    cache: CacheDep,
    _claims: WriteAdminDep,
):
    updated = await repository.update(
        account_number, currency=body.currency,
        branch_id=body.branch_id, status=body.status,
    )
    if updated is None:
        raise AccountNotFoundError(account_number)
    await cache.delete(cache_key(ENTITY, account_number))
    return updated


@router.delete("/{account_number}", response_model=AccountResponseDTO)
async def soft_delete(
    account_number: str, repository: AccountRepositoryDep, cache: CacheDep, _claims: WriteAdminDep
):
    updated = await repository.close(account_number)
    if updated is None:
        raise AccountNotFoundError(account_number)
    await cache.delete(cache_key(ENTITY, account_number))
    return updated
