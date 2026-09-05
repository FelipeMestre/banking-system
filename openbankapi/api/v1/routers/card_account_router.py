"""`card-accounts` endpoints (Credit Cards Phase 1).

`issue`/`renew` orchestrate two repositories and go through `CardAccountServiceDep`
(AGENTS.md: 2+ repos = a domain service). Everything else here is a single
repository call and goes router -> repository directly.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.card_account_dto import (
    CardAccountCreateDTO,
    CardAccountResponseDTO,
    CardAccountStatusUpdateDTO,
    CardAccountUpdateDTO,
)
from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO, CardMaskedDTO
from openbankapi.api.v1.dtos.common import PageParams
from openbankapi.config.dependencies import CardAccountRepositoryDep, CardAccountServiceDep, CardRepositoryDep
from openbankapi.domain.exceptions import CardAccountNotFoundError, InvalidCardStatusError
from openbankapi.domain.model import CARD_ACCOUNT_TRANSITIONS, CardAccountStatus

router = APIRouter(prefix="/card-accounts", tags=["card-accounts"])


def _issued_view(card_account, card) -> dict:
    return {
        "card_account": CardAccountResponseDTO.model_validate(card_account).model_dump(mode="json"),
        "card": CardIssuedDTO.model_validate(card).model_dump(mode="json"),
    }


def _masked_view(card_account, active_card) -> dict:
    return {
        "card_account": CardAccountResponseDTO.model_validate(card_account).model_dump(mode="json"),
        "card": CardMaskedDTO.model_validate(active_card).model_dump(mode="json") if active_card else None,
    }


@router.post("", status_code=201)
async def issue(body: CardAccountCreateDTO, service: CardAccountServiceDep):
    """Creates the card account and its first card atomically; the response
    includes the unmasked `card_number` (spec: "Issue creates account and
    card atomically")."""
    card_account, card = await service.issue_card_account(
        customer_id=body.customer_id,
        paying_account_id=body.paying_account_id,
        credit_limit=body.credit_limit,
    )
    return _issued_view(card_account, card)


@router.get("/{card_account_id}")
async def get(card_account_id: UUID, repository: CardAccountRepositoryDep, cards: CardRepositoryDep):
    card_account = await repository.get_by_id(card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card_account_id)
    active_card = await cards.get_active_for_account(card_account_id)
    return _masked_view(card_account, active_card)


@router.get("")
async def list_by_customer(
    customer_id: UUID,
    repository: CardAccountRepositoryDep,
    cards: CardRepositoryDep,
    page: PageParams = Depends(),
):
    result = await repository.list_by_customer(customer_id, limit=page.limit, offset=page.offset)
    items = []
    for card_account in result.items:
        active_card = await cards.get_active_for_account(card_account.id)
        items.append(_masked_view(card_account, active_card))
    return {"items": items, "total": result.total, "limit": result.limit, "offset": result.offset}


@router.put("/{card_account_id}", response_model=CardAccountResponseDTO)
async def update(card_account_id: UUID, body: CardAccountUpdateDTO, repository: CardAccountRepositoryDep):
    """Updates `credit_limit` only (spec: `PUT /card-accounts/{id}`).

    """
    updated = await repository.get_by_id(card_account_id)
    if updated is None:
        raise CardAccountNotFoundError(card_account_id)
    if body.credit_limit is not None:
        updated = await repository.update_limit(card_account_id, credit_limit=body.credit_limit)
    return updated


@router.post("/{card_account_id}/status", response_model=CardAccountResponseDTO)
async def update_status(
    card_account_id: UUID, body: CardAccountStatusUpdateDTO, repository: CardAccountRepositoryDep
):
    current = await repository.get_by_id(card_account_id)
    if current is None:
        raise CardAccountNotFoundError(card_account_id)
    target = CardAccountStatus(body.status)
    if target not in CARD_ACCOUNT_TRANSITIONS.get(current.status, frozenset()):
        raise InvalidCardStatusError(current.status.value, target.value)
    return await repository.update_status(card_account_id, status=body.status)


@router.post("/{card_account_id}/cards", status_code=201, response_model=CardIssuedDTO)
async def renew(card_account_id: UUID, service: CardAccountServiceDep):
    """Renews the account's active card; old card -> `replaced`, 409 if the
    account is not active (spec: "Renewal preserves account identity")."""
    return await service.renew_card(card_account_id)
