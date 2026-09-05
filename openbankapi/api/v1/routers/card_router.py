"""`cards` endpoints (Credit Cards Phase 1 & 2).

Blocking/reactivating a single card here is independent of the parent
`card_accounts.status` — spec: "Card and account blocking are independent".

Purchase intake (Phase 2) is added here rather than a new router: it is
card-scoped exactly like `update_status`, and reuses the same
card-lookup dependency instead of duplicating it (design decision).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends

from openbankapi.api.v1.dtos.card_dto import CardAdminListItemDTO, CardMaskedDTO, CardStatusUpdateDTO
from openbankapi.api.v1.dtos.common import PageParams
from openbankapi.api.v1.dtos.purchase_dto import PurchaseAcceptedDTO, PurchaseRequestDTO
from openbankapi.config.dependencies import (
    CardAccountRepositoryDep,
    CardRepositoryDep,
    CustomerRepositoryDep,
    ForeignExchangeCacheServiceDep,
    PublisherDep,
    SettingsDep,
)
from openbankapi.domain.exceptions import (
    CardAccountNotFoundError,
    CardNotFoundError,
    InvalidCardStatusError,
)
from openbankapi.domain.model import CARD_TRANSITIONS, CardAccountStatus, CardStatus
from openbankapi.domain.service.conversion_service import convert

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("")
async def list_all(
    cards: CardRepositoryDep,
    card_accounts: CardAccountRepositoryDep,
    customers: CustomerRepositoryDep,
    page: PageParams = Depends(),
):
    """Admin-only: every card across every customer, for the purchase-
    simulation tool's card picker — no other client needs a cross-customer
    card list. The per-card card_account/customer lookups are fine here:
    this is a bounded, paginated admin listing, not a hot path.
    """
    result = await cards.list_all(limit=page.limit, offset=page.offset)
    items = []
    for card in result.items:
        card_account = await card_accounts.get_by_id(card.card_account_id)
        customer = await customers.get(card_account.customer_id) if card_account else None
        customer_name = f"{customer.first_name} {customer.last_name}" if customer else "Unknown customer"
        items.append(
            CardAdminListItemDTO(
                id=card.id,
                card_account_id=card.card_account_id,
                card_number=card.card_number,
                status=card.status.value,
                customer_name=customer_name,
            )
        )
    return {"items": items, "total": result.total, "limit": result.limit, "offset": result.offset}


@router.post("/{card_number}/status", response_model=CardMaskedDTO)
async def update_status(card_number: str, body: CardStatusUpdateDTO, repository: CardRepositoryDep):
    current = await repository.get_by_number(card_number)
    if current is None:
        raise CardNotFoundError(card_number)
    target = CardStatus(body.status)
    if target not in CARD_TRANSITIONS.get(current.status, frozenset()):
        raise InvalidCardStatusError(current.status.value, target.value)
    return await repository.update_status(current.id, status=body.status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@router.post("/{card_number}/purchases", status_code=202, response_model=PurchaseAcceptedDTO)
async def request_purchase(
    card_number: str,
    body: PurchaseRequestDTO,
    cards: CardRepositoryDep,
    card_accounts: CardAccountRepositoryDep,
    publisher: PublisherDep,
    settings: SettingsDep,
    foreign_exchange_cache_service: ForeignExchangeCacheServiceDep,
):
    """Structural checks only — never checks available credit here.

    Authorization against `credit_limit` happens downstream in the Card
    Service Flink job, keyed on `card_id`. `credit_limit` is read fresh
    from Postgres right here (never cached) so the job never has to store
    it in Flink state (design §6).
    """
    card = await cards.get_by_number(card_number)
    if card is None:
        raise CardNotFoundError(card_number)
    if card.status is not CardStatus.ACTIVE:
        raise InvalidCardStatusError(card.status.value, "purchase")

    card_account = await card_accounts.get_by_id(card.card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card.card_account_id)
    if card_account.status is not CardAccountStatus.ACTIVE:
        raise InvalidCardStatusError(card_account.status.value, "purchase")

    amount_usd = body.amount
    applied_rate = None
    if body.currency != "USD":
        rates = await foreign_exchange_cache_service.get_rates()
        # `convert` works in integer cents (same contract as
        # `transfer_service.py`'s fee-conversion call) — convert both ways.
        amount_cents = int((body.amount * 100).to_integral_value())
        quote = convert(amount_cents, body.currency, "USD", "debit", rates)
        amount_usd = Decimal(quote["final_amount"]) / 100
        applied_rate = quote["applied_rate"]

    request_id = str(uuid.uuid4())
    wire = {
        "type": "purchase_requested",
        "request_id": request_id,
        "card_id": str(card.id),
        "card_account_id": str(card_account.id),
        "amount": str(body.amount),
        "currency": body.currency,
        "amount_usd": float(amount_usd),
        "credit_limit": float(card_account.credit_limit),
        "installments": body.installments,
        "description": body.description,
        "applied_rate": applied_rate,
        "ts": _now(),
    }
    publisher.publish(topic=settings.card_events_topic, key=str(card_account.id), value=wire)
    return PurchaseAcceptedDTO(request_id=request_id, status="pending")
