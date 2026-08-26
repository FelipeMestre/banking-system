"""`accounts` endpoints (spec §8.2).

The update route can NEVER change a balance. `AccountUpdateDTO` has no `balance`
field and `extra="forbid"` rejects one that is sent anyway (spec §11.3); beyond
that, this controller is handed an `IAccountRepository`, which has no method that
writes `balance` at all. Two independent structural guards, neither of them a
validator that someone could later relax.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..domain.exceptions import AccountNotFoundError
from ..infra.cache.interfaces.cache_service import cache_key
from .cache_aside import read_through
from .dtos.common import PageParams, PageResponse
from .dtos.account_dto import AccountCreateDTO, AccountResponseDTO, AccountUpdateDTO

ENTITY = "account"


def build_router(service, repository, cache, ttl_seconds: int) -> APIRouter:
    router = APIRouter(prefix="/accounts", tags=["accounts"])

    def _dto(entity) -> dict:
        return AccountResponseDTO.model_validate(entity).model_dump(mode="json")

    @router.post("", status_code=201, response_model=AccountResponseDTO)
    async def create(body: AccountCreateDTO):
        """`account_number` is generated server-side: it is the Kafka partition
        key, so it must be correct by construction (spec §8.2). A collision on
        the generated value is retried internally and never becomes a 500."""
        return await service.open_account(
            currency=body.currency, customer_id=body.customer_id, branch_id=body.branch_id
        )

    @router.get("", response_model=PageResponse[AccountResponseDTO])
    async def list_all(page: PageParams = Depends()):
        result = await repository.list(limit=page.limit, offset=page.offset)
        return PageResponse(
            items=[AccountResponseDTO.model_validate(i) for i in result.items],
            total=result.total, limit=result.limit, offset=result.offset,
        )

    @router.get("/{account_number}", response_model=AccountResponseDTO)
    async def get(account_number: str):
        """`balance` here is eventually consistent (spec §3.6): it lags the ledger
        by however long the account-balances consumer takes, typically a few
        hundred milliseconds. Stale is acceptable; wrong is not."""
        found = await read_through(
            cache, cache_key(ENTITY, account_number),
            lambda: repository.get_by_numero(account_number), _dto, ttl_seconds,
        )
        if found is None:
            raise AccountNotFoundError(account_number)
        return found

    @router.put("/{account_number}", response_model=AccountResponseDTO)
    async def update(account_number: str, body: AccountUpdateDTO):
        updated = await repository.update(
            account_number, currency=body.currency,
            branch_id=body.branch_id, status=body.status,
        )
        if updated is None:
            raise AccountNotFoundError(account_number)
        await cache.delete(cache_key(ENTITY, account_number))
        return updated

    @router.delete("/{account_number}", response_model=AccountResponseDTO)
    async def soft_delete(account_number: str):
        updated = await repository.close(account_number)
        if updated is None:
            raise AccountNotFoundError(account_number)
        await cache.delete(cache_key(ENTITY, account_number))
        return updated

    return router
