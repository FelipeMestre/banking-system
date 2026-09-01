"""`accounts` endpoints (spec §8.2).

The update route can NEVER change a balance. `AccountUpdateDTO` has no `balance`
field and `extra="forbid"` rejects one that is sent anyway (spec §11.3); beyond
that, this controller is handed an `IAccountRepository`, which has no method that
writes `balance` at all. Two independent structural guards, neither of them a
validator that someone could later relax.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.account_dto import AccountCreateDTO, AccountResponseDTO, AccountUpdateDTO
from openbankapi.api.v1.dtos.common import PageParams, PageResponse
from openbankapi.api.v1.dtos.transaction_dto import TransactionsPageDTO, TransactionsPageParams
from openbankapi.api.v1.services.cache_aside import read_through
from openbankapi.config.dependencies import (
    AccountRepositoryDep,
    AccountServiceDep,
    CacheDep,
    CurrentCustomerDep,
    SettingsDep,
    TransactionServiceDep,
)
from openbankapi.domain.exceptions import AccountAccessForbiddenError, AccountNotFoundError
from openbankapi.infra.cache.interfaces import cache_key

ENTITY = "account"
router = APIRouter(prefix="/accounts", tags=["accounts"])


def _dto(entity) -> dict:
    return AccountResponseDTO.model_validate(entity).model_dump(mode="json")


@router.post("", status_code=201, response_model=AccountResponseDTO)
async def create(body: AccountCreateDTO, service: AccountServiceDep):
    """`account_number` is generated server-side: it is the Kafka partition
    key, so it must be correct by construction (spec §8.2). A collision on
    the generated value is retried internally and never becomes a 500."""
    return await service.open_account(
        currency=body.currency, customer_id=body.customer_id, branch_id=body.branch_id
    )


@router.get("", response_model=PageResponse[AccountResponseDTO])
async def list_all(
    repository: AccountRepositoryDep, customer: CurrentCustomerDep, page: PageParams = Depends()
):
    """Scoped to the caller's own accounts (spec §2.1) — never the whole table."""
    result = await repository.list_by_customer(customer.id, limit=page.limit, offset=page.offset)
    return PageResponse(
        items=[AccountResponseDTO.model_validate(i) for i in result.items],
        total=result.total, limit=result.limit, offset=result.offset,
    )


@router.get("/{account_number}/transactions", response_model=TransactionsPageDTO)
async def list_transactions(
    account_number: str,
    repository: AccountRepositoryDep,
    customer: CurrentCustomerDep,
    service: TransactionServiceDep,
    page: TransactionsPageParams = Depends(),
):
    """Newest-first, keyset-paginated (spec §3.3). 403s rather than 404s when
    the account exists but belongs to someone else (spec §3.4) — the caller
    must never learn account_number existence from the status code alone."""
    account = await repository.get_by_account_number(account_number)
    if account is None:
        raise AccountNotFoundError(account_number)
    if account.customer_id != customer.id:
        raise AccountAccessForbiddenError(account_number)
    result = await service.list_for_account(account_number, limit=page.limit, cursor=page.cursor)
    return TransactionsPageDTO(items=result.items, next_cursor=result.next_cursor)


@router.get("/{account_number}", response_model=AccountResponseDTO)
async def get(
    account_number: str, repository: AccountRepositoryDep, cache: CacheDep, settings: SettingsDep
):
    """`balance` here is eventually consistent (spec §3.6): it lags the ledger
    by however long the account-balances consumer takes, typically a few
    hundred milliseconds. Stale is acceptable; wrong is not."""
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
async def soft_delete(account_number: str, repository: AccountRepositoryDep, cache: CacheDep):
    updated = await repository.close(account_number)
    if updated is None:
        raise AccountNotFoundError(account_number)
    await cache.delete(cache_key(ENTITY, account_number))
    return updated
