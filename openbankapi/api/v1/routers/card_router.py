"""`cards` endpoints (Credit Cards Phase 1).

Blocking/reactivating a single card here is independent of the parent
`card_accounts.status` — spec: "Card and account blocking are independent".
"""
from __future__ import annotations

from fastapi import APIRouter

from openbankapi.api.v1.dtos.card_dto import CardMaskedDTO, CardStatusUpdateDTO
from openbankapi.config.dependencies import CardRepositoryDep
from openbankapi.domain.exceptions import CardNotFoundError, InvalidCardStatusError
from openbankapi.domain.model import CARD_TRANSITIONS, CardStatus

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post("/{card_number}/status", response_model=CardMaskedDTO)
async def update_status(card_number: str, body: CardStatusUpdateDTO, repository: CardRepositoryDep):
    current = await repository.get_by_number(card_number)
    if current is None:
        raise CardNotFoundError(card_number)
    target = CardStatus(body.status)
    if target not in CARD_TRANSITIONS.get(current.status, frozenset()):
        raise InvalidCardStatusError(current.status.value, target.value)
    return await repository.update_status(current.id, status=body.status)
