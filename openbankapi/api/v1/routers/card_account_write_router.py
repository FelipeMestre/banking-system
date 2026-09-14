"""`card-accounts` write endpoints (Credit Cards Phase 1, split from `card_account_router`).

Mutating routes under `/card-accounts`:
- `POST /card-accounts` (issue)
- `PUT /card-accounts/{id}` (update_limit)
- `POST /card-accounts/{id}/status` (update_status)
- `POST /card-accounts/{id}/cards` (renew)
- `POST /card-accounts/{id}/payments` (payment request)

Read routes remain in `card_account_read_router`.
`card_account_router` re-exports both so the mount is unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter

from openbankapi.api.v1.dtos.card_account_dto import (
    CardAccountCreateDTO,
    CardAccountRenewDTO,
    CardAccountResponseDTO,
    CardAccountStatusUpdateDTO,
    CardAccountUpdateDTO,
)
from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO
from openbankapi.api.v1.dtos.card_payment_dto import CardPaymentAcceptedDTO, CardPaymentRequestDTO
from openbankapi.config.dependencies import (
    AccountRepositoryDep,
    AdminActionRepositoryDep,
    AdminIdentityDep,
    CardAccountRepositoryDep,
    CardAccountServiceDep,
    CardMovementRepositoryDep,
    CardRepositoryDep,
    ForeignExchangeCacheServiceDep,
    PublisherDep,
    SettingsDep,
    WriteAdminDep,
)
from openbankapi.domain.exceptions import (
    CardAccountNotCloseableError,
    CardAccountNotFoundError,
    InvalidCardStatusError,
)
from openbankapi.domain.model import (
    CARD_ACCOUNT_TRANSITIONS,
    CardAccountStatus,
)
from openbankapi.domain.service.conversion_service import convert

router = APIRouter(prefix="/card-accounts", tags=["card-accounts"])


def _issued_view(card_account, card) -> dict:
    return {
        "card_account": CardAccountResponseDTO.model_validate(card_account).model_dump(mode="json"),
        "card": CardIssuedDTO.model_validate(card).model_dump(mode="json"),
    }


@router.post("", status_code=201)
async def issue(
    body: CardAccountCreateDTO,
    service: CardAccountServiceDep,
    admin_actions: AdminActionRepositoryDep,
    admin_id: AdminIdentityDep,
):
    """Creates the card account and its first card atomically; the response
    includes the unmasked `card_number` (spec: "Issue creates account and
    card atomically")."""
    card_account, card = await service.issue_card_account(
        customer_id=body.customer_id,
        paying_account_id=body.paying_account_id,
        credit_limit=body.credit_limit,
    )
    await admin_actions.record(
        card_account_id=card_account.id,
        action="issue",
        admin_id=admin_id,
        reason=body.reason,
        details={
            "card_account_id": str(card_account.id),
            "card_id": str(card.id),
            "credit_limit": str(body.credit_limit),
        },
    )
    return _issued_view(card_account, card)


@router.put("/{card_account_id}", response_model=CardAccountResponseDTO)
async def update(
    card_account_id: UUID,
    body: CardAccountUpdateDTO,
    repository: CardAccountRepositoryDep,
    admin_actions: AdminActionRepositoryDep,
    admin_id: AdminIdentityDep,
):
    """Updates `credit_limit` only (spec: `PUT /card-accounts/{id}`)."""
    current = await repository.get_by_id(card_account_id)
    if current is None:
        raise CardAccountNotFoundError(card_account_id)
    updated = current
    if body.credit_limit is not None:
        updated = await repository.update_limit(card_account_id, credit_limit=body.credit_limit)
        await admin_actions.record(
            card_account_id=card_account_id,
            action="update_limit",
            admin_id=admin_id,
            reason=body.reason,
            details={"from_limit": str(current.credit_limit), "to_limit": str(body.credit_limit)},
        )
    return updated


@router.post("/{card_account_id}/status", response_model=CardAccountResponseDTO)
async def update_status(
    card_account_id: UUID,
    body: CardAccountStatusUpdateDTO,
    repository: CardAccountRepositoryDep,
    movements: CardMovementRepositoryDep,
    admin_actions: AdminActionRepositoryDep,
    admin_id: AdminIdentityDep,
):
    current = await repository.get_by_id(card_account_id)
    if current is None:
        raise CardAccountNotFoundError(card_account_id)
    target = CardAccountStatus(body.status)
    if target not in CARD_ACCOUNT_TRANSITIONS.get(current.status, frozenset()):
        raise InvalidCardStatusError(current.status.value, target.value)

    # Balance is only ever computed/guarded for a close (design D3) — every
    # other transition (e.g. active<->blocked) never queries it.
    if target is CardAccountStatus.CLOSED:
        balance = await movements.compute_current_balance(card_account_id)
        if balance > 0:
            raise CardAccountNotCloseableError(card_account_id, balance)

    updated = await repository.update_status(card_account_id, status=body.status)
    await admin_actions.record(
        card_account_id=card_account_id,
        action="update_status",
        admin_id=admin_id,
        reason=body.reason,
        details={"from_status": current.status.value, "to_status": target.value},
    )
    return updated


@router.post("/{card_account_id}/cards", status_code=201, response_model=CardIssuedDTO)
async def renew(
    card_account_id: UUID,
    service: CardAccountServiceDep,
    cards: CardRepositoryDep,
    admin_actions: AdminActionRepositoryDep,
    admin_id: AdminIdentityDep,
    body: CardAccountRenewDTO = CardAccountRenewDTO(),
):
    """Renews the account's active card; old card -> `replaced`, 409 if the
    account is not active (spec: "Renewal preserves account identity").
    Audits both old and new `card_number`/`expiration_date` (design D2)."""
    old_card = await cards.get_active_for_account(card_account_id)
    new_card = await service.renew_card(card_account_id)
    await admin_actions.record(
        card_account_id=card_account_id,
        action="renew",
        admin_id=admin_id,
        reason=body.reason,
        details={
            "old_card_id": str(old_card.id) if old_card else None,
            "new_card_id": str(new_card.id),
            "old_number": old_card.card_number if old_card else None,
            "new_number": new_card.card_number,
            "old_expiry": old_card.expiration_date.isoformat() if old_card else None,
            "new_expiry": new_card.expiration_date.isoformat(),
        },
    )
    return new_card


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@router.post(
    "/{card_account_id}/payments", status_code=202, response_model=CardPaymentAcceptedDTO
)
async def request_payment(
    card_account_id: UUID,
    body: CardPaymentRequestDTO,
    card_accounts: CardAccountRepositoryDep,
    cards: CardRepositoryDep,
    accounts: AccountRepositoryDep,
    publisher: PublisherDep,
    settings: SettingsDep,
    foreign_exchange_cache_service: ForeignExchangeCacheServiceDep,
):
    card_account = await card_accounts.get_by_id(card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card_account_id)

    active_card = await cards.get_active_for_account(card_account_id)
    if active_card is None:
        raise InvalidCardStatusError("none", "payment")

    paying_account = await accounts.get_by_id(card_account.paying_account_id)
    if paying_account is None:
        raise CardAccountNotFoundError(card_account.paying_account_id)

    amount_usd = body.amount
    conversion = None
    if paying_account.currency != "USD":
        rates = await foreign_exchange_cache_service.get_rates()
        quote = convert(body.amount, paying_account.currency, "USD", "debit", rates)
        amount_usd = quote["final_amount"]
        conversion = quote["applied_rate"]

    request_id = str(uuid.uuid4())
    wire = {
        "type": "payment_requested",
        "request_id": request_id,
        "account_id": paying_account.account_number,
        "destination_account": active_card.card_number,
        "card_account_id": str(card_account_id),
        "card_id": str(active_card.id),
        "amount": body.amount,
        "amount_usd": amount_usd,
        "ts": _now(),
    }
    if conversion is not None:
        wire["conversion"] = conversion
    publisher.publish(
        topic=settings.account_events_topic, key=paying_account.account_number, value=wire
    )
    return CardPaymentAcceptedDTO(request_id=request_id, status="pending")
