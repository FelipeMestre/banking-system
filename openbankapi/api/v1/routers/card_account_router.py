"""`card-accounts` endpoints (Credit Cards Phase 1).

`issue`/`renew` orchestrate two repositories and go through `CardAccountServiceDep`
(AGENTS.md: 2+ repos = a domain service). Everything else here is a single
repository call and goes router -> repository directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from openbankapi.api.v1.dtos.card_account_dto import (
    CardAccountCreateDTO,
    CardAccountResponseDTO,
    CardAccountStatusUpdateDTO,
    CardAccountUpdateDTO,
)
from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO, CardMaskedDTO
from openbankapi.api.v1.dtos.card_payment_dto import CardPaymentAcceptedDTO, CardPaymentRequestDTO
from openbankapi.api.v1.dtos.card_usage_dto import CardMovementDTO, UsedCreditEstimateDTO
from openbankapi.api.v1.dtos.common import DEFAULT_LIMIT, MAX_LIMIT, PageParams, PageResponse
from openbankapi.api.v1.dtos.statement_dto import InstallmentPayoffDTO, StatementDTO
from openbankapi.config.dependencies import (
    AccountRepositoryDep,
    AppliedRateRepositoryDep,
    CardAccountRepositoryDep,
    CardAccountServiceDep,
    CardMovementRepositoryDep,
    CardRepositoryDep,
    CurrentCustomerDep,
    ForeignExchangeCacheServiceDep,
    InstallmentRepositoryDep,
    PublisherDep,
    SettingsDep,
    StatementRepositoryDep,
)
from openbankapi.domain.exceptions import (
    CardAccountAccessForbiddenError,
    CardAccountNotFoundError,
    InvalidCardStatusError,
    StatementNotFoundError,
)
from openbankapi.domain.model import (
    CARD_ACCOUNT_TRANSITIONS,
    CardAccountStatus,
    CardMovement,
    CardMovementType,
    Statement,
)
from openbankapi.domain.service.conversion_service import convert
from openbankapi.infra.pdf.statement_pdf_generator import render as render_statement_pdf

router = APIRouter(prefix="/card-accounts", tags=["card-accounts"])

# `PURCHASE`/`FEE`/`INTEREST` increase what a customer owes; `PAYMENT`/`REFUND`
# reduce it. `DECLINED` is excluded entirely — it never happened financially.
_INCREASES_USAGE = frozenset({CardMovementType.PURCHASE, CardMovementType.FEE, CardMovementType.INTEREST})
_REDUCES_USAGE = frozenset({CardMovementType.PAYMENT, CardMovementType.REFUND})


async def _owned_card_account(card_account_id: UUID, repository: CardAccountRepositoryDep, customer):
    card_account = await repository.get_by_id(card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card_account_id)
    if card_account.customer_id != customer.id:
        raise CardAccountAccessForbiddenError(card_account_id)
    return card_account


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


@router.get("/{card_account_id}/used-credit-estimate", response_model=UsedCreditEstimateDTO)
async def used_credit_estimate(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    movements: CardMovementRepositoryDep,
    customer: CurrentCustomerDep,
):
    """A derived approximation, never the Flink Card Service's authoritative
    `used_credit` state — the `-estimate` suffix and `is_estimate` field are
    the honesty signal (spec: "Derived Used-Credit Approximation Endpoint").
    Scoped by `card_account_id`, not the currently active card alone, so a
    renewed card's pre-renewal history is still counted (design amendment)."""
    card_account = await _owned_card_account(card_account_id, repository, customer)
    rows = await movements.get_by_card_account_id(card_account_id)

    total = Decimal(0)
    for row in rows:
        if row.movement_type in _INCREASES_USAGE:
            total += row.amount
        elif row.movement_type in _REDUCES_USAGE:
            total -= row.amount
        # DECLINED (and any other type) never happened financially — excluded.

    return UsedCreditEstimateDTO(
        card_account_id=card_account_id,
        used_credit_estimate=max(total, Decimal(0)),
        credit_limit=card_account.credit_limit,
        movement_count=len(rows),
    )


async def _movement_dto(
    row: CardMovement, applied_rates: AppliedRateRepositoryDep, installments: InstallmentRepositoryDep
) -> CardMovementDTO:
    rate = await applied_rates.get_by_id(row.applied_rate_id) if row.applied_rate_id else None
    splits = (
        await installments.get_by_movement_id(row.id)
        if row.movement_type == CardMovementType.PURCHASE
        else []
    )
    return CardMovementDTO(
        id=row.id,
        movement_type=row.movement_type.value,
        amount=row.amount,
        currency=row.currency,
        description=row.description,
        decline_reason=row.decline_reason,
        occurred_at=row.occurred_at or row.created_at,
        fx_pair=rate.pair if rate else None,
        fx_applied_rate=rate.applied_rate if rate else None,
        installment_count=len(splits) if len(splits) > 1 else None,
        installment_amount=splits[0].amount if len(splits) > 1 else None,
    )


async def _installment_plan_movement_ids(
    rows: List[CardMovement], installments: InstallmentRepositoryDep
) -> set:
    """Ids of purchase movements that are the parent of a multi-installment
    plan. Such a movement occurred once, at purchase time — it must never be
    date-range-matched into a later statement's cycle, because each cycle
    only ever bills ONE installment of that plan (`mark_billed`). The billed
    installment itself (not this parent row) is what represents that plan in
    a given cycle — see `_billed_installment_dtos` below."""
    plan_ids = set()
    for row in rows:
        if row.movement_type != CardMovementType.PURCHASE:
            continue
        splits = await installments.get_by_movement_id(row.id)
        if len(splits) > 1:
            plan_ids.add(row.id)
    return plan_ids


def _in_statement_period(row: CardMovement, statement: Statement) -> bool:
    occurred = (row.occurred_at or row.created_at).date()
    return statement.period_start <= occurred <= statement.period_end


async def _period_movements(
    statement: Statement, all_rows: List[CardMovement], installments: InstallmentRepositoryDep
) -> List[CardMovement]:
    """Every movement genuinely tied to this billing cycle by *when it
    happened* — single-charge purchases and every other movement type
    (payments, fees, interest, refunds, declines) whose `occurred_at` falls
    inside `[period_start, period_end]`. Multi-installment purchase movements
    are excluded here on purpose (see `_installment_plan_movement_ids`) —
    they are represented per-cycle by `_billed_installment_dtos` instead,
    which ties them to the statement `mark_billed` actually assigned rather
    than to a purchase date that may not even fall in this cycle."""
    plan_ids = await _installment_plan_movement_ids(all_rows, installments)
    return [
        row for row in all_rows if row.id not in plan_ids and _in_statement_period(row, statement)
    ]


async def _billed_installment_dtos(
    statement: Statement,
    rows_by_id: dict,
    installments: InstallmentRepositoryDep,
    applied_rates: AppliedRateRepositoryDep,
) -> List[CardMovementDTO]:
    """One `CardMovementDTO` per installment this exact statement billed
    (`get_by_statement_id` — the inverse of `mark_billed`), carrying only
    that installment's own amount, not the parent purchase's full amount."""
    billed = await installments.get_by_statement_id(statement.id)
    dtos = []
    for installment in billed:
        parent = rows_by_id.get(installment.card_movement_id)
        total_installments = await installments.get_total_installments(installment.card_movement_id)
        rate = (
            await applied_rates.get_by_id(parent.applied_rate_id)
            if parent is not None and parent.applied_rate_id
            else None
        )
        occurred_at = datetime.combine(installment.due_date, datetime.min.time(), tzinfo=timezone.utc)
        dtos.append(
            CardMovementDTO(
                id=installment.id,
                movement_type=CardMovementType.PURCHASE.value,
                amount=installment.amount,
                currency=parent.currency if parent is not None else "USD",
                description=parent.description if parent is not None else None,
                decline_reason=None,
                occurred_at=occurred_at,
                fx_pair=rate.pair if rate else None,
                fx_applied_rate=rate.applied_rate if rate else None,
                installment_count=total_installments,
                installment_amount=installment.amount,
            )
        )
    return dtos


async def _owned_statement(
    card_account_id: UUID, statement_id: UUID, statements: StatementRepositoryDep
) -> Statement:
    statement = await statements.get_by_id(statement_id)
    if statement is None or statement.card_account_id != card_account_id:
        # Deliberately not distinguished from "doesn't exist" — see
        # `StatementNotFoundError`'s own docstring.
        raise StatementNotFoundError(statement_id)
    return statement


@router.get("/{card_account_id}/movements", response_model=PageResponse[CardMovementDTO])
async def list_movements(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    movements: CardMovementRepositoryDep,
    applied_rates: AppliedRateRepositoryDep,
    installments: InstallmentRepositoryDep,
    statements: StatementRepositoryDep,
    customer: CurrentCustomerDep,
    page: PageParams = Depends(),
    statement_id: Optional[UUID] = Query(
        default=None,
        description=(
            "Scope the list to one billing cycle. A single-charge purchase "
            "matches by date falling inside that statement's period; a "
            "billed installment matches by the statement it was actually "
            "billed onto, regardless of its parent purchase's date."
        ),
    ),
):
    """Paginated, newest-first (spec: "Movements List Endpoint"). Per-row
    `applied_rates`/`installments` lookups mirror `card_router.py::list_all`'s
    justified N+1 precedent for a bounded, paginated listing — not a batched
    join."""
    await _owned_card_account(card_account_id, repository, customer)

    all_rows = await movements.get_by_card_account_id(card_account_id)

    if statement_id is not None:
        statement = await _owned_statement(card_account_id, statement_id, statements)
        rows_by_id = {row.id: row for row in all_rows}
        period_rows = await _period_movements(statement, all_rows, installments)
        items = [await _movement_dto(row, applied_rates, installments) for row in period_rows]
        items += await _billed_installment_dtos(statement, rows_by_id, installments, applied_rates)
        items.sort(key=lambda dto: dto.occurred_at, reverse=True)
        total = len(items)
        page_items = items[page.offset : page.offset + page.limit]
        return PageResponse(items=page_items, total=total, limit=page.limit, offset=page.offset)

    total = len(all_rows)
    page_rows = all_rows[page.offset : page.offset + page.limit]
    items = [await _movement_dto(row, applied_rates, installments) for row in page_rows]
    return PageResponse(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{card_account_id}/statements", response_model=List[StatementDTO])
async def list_statements(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    statements: StatementRepositoryDep,
    customer: CurrentCustomerDep,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    """Every closed billing cycle for this account, newest first — powers the
    customer-facing billing-cycle tab strip."""
    await _owned_card_account(card_account_id, repository, customer)
    rows = await statements.list_by_card_account_id(card_account_id, limit)
    return [StatementDTO.model_validate(row) for row in rows]


@router.get("/{card_account_id}/installment-payoff", response_model=InstallmentPayoffDTO)
async def installment_payoff(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    installments: InstallmentRepositoryDep,
    customer: CurrentCustomerDep,
):
    """The "settle all installment balances early" amount — a plain sum of
    unbilled installment amounts, safe to expose because installments carry
    0% interest (see `InstallmentPayoffDTO`)."""
    await _owned_card_account(card_account_id, repository, customer)
    payoff_amount = await installments.sum_unbilled(card_account_id)
    return InstallmentPayoffDTO(card_account_id=card_account_id, payoff_amount=payoff_amount)


@router.get("/{card_account_id}/statements/{statement_id}/pdf")
async def download_statement_pdf(
    card_account_id: UUID,
    statement_id: UUID,
    repository: CardAccountRepositoryDep,
    statements: StatementRepositoryDep,
    movements: CardMovementRepositoryDep,
    installments: InstallmentRepositoryDep,
    customer: CurrentCustomerDep,
):
    """Renders the real statement PDF on demand — distinct from the
    placeholder `render_statement_pdf(statement, [], billed_installments)`
    call `close_statement` makes at close time (that one intentionally has no
    movements yet); this one assembles the real period-scoped movements plus
    the exact installments this statement billed."""
    await _owned_card_account(card_account_id, repository, customer)
    statement = await _owned_statement(card_account_id, statement_id, statements)

    all_rows = await movements.get_by_card_account_id(card_account_id)
    period_rows = await _period_movements(statement, all_rows, installments)
    billed_installments = await installments.get_by_statement_id(statement.id)

    pdf_bytes = render_statement_pdf(statement, period_rows, billed_installments)
    filename = f"statement-{statement.period_end.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    """Pays down a card account's balance from its FIXED paying account
    (Credit Cards Phase 3, spec: card-account-payments-api). The paying
    account is never a request field — it is resolved from
    `card_accounts.paying_account_id`, set at issuance and immutable.

    Structural checks only, mirroring `card_router.py::request_purchase`'s
    own reasoning: no credit-limit check happens here or anywhere on the
    payment path (spec: Non-Requirements) — the account-service Flink job is
    the sole authority on whether the paying account can afford this.
    """
    card_account = await card_accounts.get_by_id(card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card_account_id)

    active_card = await cards.get_active_for_account(card_account_id)
    if active_card is None:
        raise InvalidCardStatusError("none", "payment")

    paying_account = await accounts.get_by_id(card_account.paying_account_id)
    if paying_account is None:
        raise CardAccountNotFoundError(card_account.paying_account_id)

    # `amount` (what the paying account is debited) stays in the account's own
    # currency, unconverted — the account-service reservation is always in the
    # account's own balance currency. `amount_usd` (what card-service's
    # `used_credit` is reduced by) is the only value that ever needs
    # converting, reusing `card_router.py::request_purchase`'s exact
    # `convert(amount_cents, currency, "USD", "debit", rates)` call shape.
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
        # The paying account this debits — account-service's `shard_key_of`
        # reads this field to route the event to the right keyed partition.
        # Every other account_events type carries it; without it here,
        # `shard_key_of` falls back to `event["source_account"]`, which this
        # event has never had, raising KeyError and silently dropping the
        # whole record as unroutable before `decide()` ever runs.
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
