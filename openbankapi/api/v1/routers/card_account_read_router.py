"""`card-accounts` read endpoints (Credit Cards Phase 1, split from `card_account_router`).

This module owns all GET/read-only routes under `/card-accounts`:
- `GET /card-accounts/{id}`
- `GET /card-accounts?customer_id=`
- `GET /card-accounts/{id}/used-credit-estimate`
- `GET /card-accounts/{id}/movements`
- `GET /card-accounts/{id}/statements`
- `GET /card-accounts/{id}/installment-payoff`
- `GET /card-accounts/{id}/statements/{statement_id}/pdf`

Mutating routes live in `card_account_write_router` (see 6.0 Housekeeping).
`card_account_router` re-exports both via `include_router` so the mount in
`openbankapi/api/v1/main.py` is unchanged.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from openbankapi.api.v1.dtos.card_account_dto import CardAccountResponseDTO
from openbankapi.api.v1.dtos.card_dto import CardMaskedDTO
from openbankapi.api.v1.dtos.card_usage_dto import CardMovementDTO, UsedCreditEstimateDTO
from openbankapi.api.v1.dtos.common import DEFAULT_LIMIT, MAX_LIMIT, PageParams, PageResponse
from openbankapi.api.v1.dtos.current_cycle_dto import CurrentCycleResponseDTO
from openbankapi.api.v1.dtos.statement_dto import InstallmentPayoffDTO, StatementDTO
from openbankapi.config.dependencies import (
    AppliedRateRepositoryDep,
    CardAccountRepositoryDep,
    CardMovementRepositoryDep,
    CardRepositoryDep,
    CurrentCustomerDep,
    CurrentCycleProjectionServiceDep,
    InstallmentRepositoryDep,
    StatementRepositoryDep,
)
from openbankapi.domain.exceptions import (
    CardAccountAccessForbiddenError,
    CardAccountNotFoundError,
    StatementNotFoundError,
)
from openbankapi.domain.model import CardMovement, CardMovementType, Statement
from openbankapi.infra.pdf.statement_pdf_generator import render as render_statement_pdf

router = APIRouter(prefix="/card-accounts", tags=["card-accounts"])

_INCREASES_USAGE = frozenset({CardMovementType.PURCHASE, CardMovementType.FEE, CardMovementType.INTEREST})
_REDUCES_USAGE = frozenset({CardMovementType.PAYMENT, CardMovementType.REFUND})


async def _owned_card_account(card_account_id: UUID, repository: CardAccountRepositoryDep, customer):
    card_account = await repository.get_by_id(card_account_id)
    if card_account is None:
        raise CardAccountNotFoundError(card_account_id)
    if card_account.customer_id != customer.id:
        raise CardAccountAccessForbiddenError(card_account_id)
    return card_account


def _masked_view(card_account, active_card) -> dict:
    return {
        "card_account": CardAccountResponseDTO.model_validate(card_account).model_dump(mode="json"),
        "card": CardMaskedDTO.model_validate(active_card).model_dump(mode="json") if active_card else None,
    }


def _masked_listing_view(card_account, active_card) -> dict:
    """Same as `_masked_view`, minus `used_credit` — B1 requires the admin
    listing to never expose it (design: keep the bulk listing off the
    per-account Flink projection read, unlike the single-account `GET`)."""
    view = _masked_view(card_account, active_card)
    view["card_account"].pop("used_credit", None)
    return view


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
    status: Optional[str] = Query(default=None, pattern="^(active|blocked|closed)$"),
):
    result = await repository.list_by_customer(
        customer_id, limit=page.limit, offset=page.offset, status=status
    )
    items = []
    for card_account in result.items:
        active_card = await cards.get_active_for_account(card_account.id)
        items.append(_masked_listing_view(card_account, active_card))
    return {"items": items, "total": result.total, "limit": result.limit, "offset": result.offset}


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
    since: Optional[date] = Query(
        default=None,
        description=(
            "Scope the list to the still-open cycle: movements with "
            "occurred_at/created_at date >= since, open-ended through today. "
            "Mutually exclusive with statement_id — no Statement row exists "
            "yet for the open cycle, so statement_id structurally cannot "
            "express this filter."
        ),
    ),
):
    if statement_id is not None and since is not None:
        raise HTTPException(
            status_code=422, detail="statement_id and since are mutually exclusive"
        )

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

    if since is not None:
        plan_ids = await _installment_plan_movement_ids(all_rows, installments)
        since_rows = [
            row for row in all_rows
            if row.id not in plan_ids and (row.occurred_at or row.created_at).date() >= since
        ]
        since_rows.sort(key=lambda row: row.occurred_at or row.created_at, reverse=True)
        total = len(since_rows)
        page_rows = since_rows[page.offset : page.offset + page.limit]
        items = [await _movement_dto(row, applied_rates, installments) for row in page_rows]
        return PageResponse(items=items, total=total, limit=page.limit, offset=page.offset)

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
    """`payable` is `True` for exactly one row — the single most-recently-
    closed statement (`get_latest`), and only while `today <= due_date` —
    never reimplemented on the frontend (design D7). An explicit
    `get_latest()` call identifies that row rather than trusting
    `list_by_card_account_id`'s ordering, so this stays correct even if that
    ordering guarantee ever changes."""
    await _owned_card_account(card_account_id, repository, customer)
    rows = await statements.list_by_card_account_id(card_account_id, limit)
    latest = await statements.get_latest(card_account_id)
    today = date.today()
    return [
        StatementDTO(
            **{**row.__dict__, "status": row.status.value},
            payable=(latest is not None and row.id == latest.id and today <= row.due_date),
        )
        for row in rows
    ]


@router.get("/{card_account_id}/current-cycle", response_model=CurrentCycleResponseDTO)
async def current_cycle(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    projection_service: CurrentCycleProjectionServiceDep,
    customer: CurrentCustomerDep,
):
    """Live, never-persisted projection of the still-open billing cycle —
    computed fresh on every call (spec: "Projection is read-only and never
    stale"). Always payable: this is the one target that is never gated by a
    due date, unlike the most-recently-closed statement above."""
    await _owned_card_account(card_account_id, repository, customer)
    projection = await projection_service.project(card_account_id, today=date.today())
    return CurrentCycleResponseDTO(
        period_start=projection.period_start,
        projected_period_end=projection.projected_period_end,
        overdue_from_previous_cycle=projection.overdue_from_previous_cycle,
        interest_on_overdue=projection.interest_on_overdue,
        new_purchases_this_cycle=projection.new_purchases_this_cycle,
        total_to_pay=projection.total_to_pay,
        payable=projection.is_payable,
    )


@router.get("/{card_account_id}/installment-payoff", response_model=InstallmentPayoffDTO)
async def installment_payoff(
    card_account_id: UUID,
    repository: CardAccountRepositoryDep,
    installments: InstallmentRepositoryDep,
    customer: CurrentCustomerDep,
):
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
