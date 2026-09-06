"""Admin manual-trigger endpoints for the Credit Cards Phase 4 monthly-batch
jobs (`batch-worker`'s hourly `python -m openbankapi.batch.run_once`).

Testing tool only — same spirit as `card_router.py`'s admin-only `GET /cards`
purchase-simulation listing: no extra auth beyond whatever the rest of this
API already requires, since this lets an admin exercise the real hourly job
on demand for testing instead of waiting for the cron or faking server time.
These are ADDITIONAL manual triggers alongside the real scheduled job, not a
replacement for it — `batch-worker`'s own cron/Docker setup is untouched.

Both endpoints call the exact same real functions `batch/run_once.py` calls
(`check_and_close_if_due`, `StatementService.run_due_date_check`) — nothing
here reimplements close/due-date logic. The only difference from the
standalone script is where the repositories come from: `batch/run_once.py`
builds its own composition root because a plain script has no ASGI request
to hang `Depends` off of; this router uses the same `Depends`-injected,
request-scoped repositories every other endpoint uses, sharing the one
request's session/transaction.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter

from openbankapi.api.v1.dtos.batch_dto import DueDateCheckRunResultDTO, MonthlyCloseRunResultDTO
from openbankapi.batch.run_once import check_and_close_if_due
from openbankapi.config.dependencies import (
    CardAccountRepositoryDep,
    SettingsDep,
    StatementRepositoryDep,
    StatementServiceDep,
)

router = APIRouter(prefix="/admin/batch", tags=["admin-batch"])


@router.post("/monthly-close", response_model=MonthlyCloseRunResultDTO)
async def run_monthly_close(
    statement_service: StatementServiceDep,
    statements: StatementRepositoryDep,
    card_accounts: CardAccountRepositoryDep,
    settings: SettingsDep,
):
    """Runs today's equivalent of the hourly worker's close check across
    every non-closed card account, using today's REAL date (never a faked
    one — this triggers the real job, it does not let the caller override
    "today"). `check_and_close_if_due` is downtime-safe on its own: it
    computes the intended close date per account and catches up any missed
    periods, exactly as the real cron would."""
    today = date.today()
    closed_statement_ids: list[UUID] = []
    closed_card_account_ids: list[UUID] = []
    for card_account_id in await card_accounts.list_active_ids():
        statement = await check_and_close_if_due(
            statement_service, statements, card_accounts, card_account_id, today, settings.close_day
        )
        if statement is not None:
            closed_statement_ids.append(statement.id)
            closed_card_account_ids.append(card_account_id)
    return MonthlyCloseRunResultDTO(
        closed_count=len(closed_statement_ids),
        statement_ids=closed_statement_ids,
        card_account_ids=closed_card_account_ids,
    )


@router.post("/due-date-check", response_model=DueDateCheckRunResultDTO)
async def run_due_date_check(statement_service: StatementServiceDep):
    """Runs today's due-date finalization + late-fee pass — the same
    `StatementService.run_due_date_check` the real cron calls, for today's
    REAL date."""
    summary = await statement_service.run_due_date_check(date.today())
    return DueDateCheckRunResultDTO(
        finalized_count=summary.finalized_count,
        late_fees_applied_count=summary.late_fees_applied_count,
    )
