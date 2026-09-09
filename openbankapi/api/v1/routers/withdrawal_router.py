"""POST /admin/withdrawals — sync admin cash withdrawal with FX and waiter.

Mirrors `deposit_router.py` almost exactly. The one meaningful directional
difference: `convert(..., "debit", ...)` instead of `"credit"`, since the
customer's own balance decreases. Unlike a deposit, a withdrawal can be
DECLINED (insufficient funds) — an ATM-style resolved business outcome, still
returned as HTTP 200 with `approved: false`, never an exception.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from openbankapi.api.v1.dtos.withdrawal_dto import WithdrawalRequestDTO, WithdrawalResponseDTO
from openbankapi.config.dependencies import (
    ForeignExchangeCacheServiceDep,
    PublisherDep,
    SettingsDep,
    WithdrawalStatusRegistryDep,
    require_permissions,
)
from openbankapi.domain.service.conversion_service import convert
from openbankapi.infra.database.interfaces.account_repository import IAccountRepository
from openbankapi.infra.database.config.session import DbSession  # noqa: F401
from openbankapi.config.dependencies import AccountRepositoryDep

WriteAdminDep = Annotated[dict, Depends(require_permissions("write:admin"))]

router = APIRouter(tags=["withdrawals"])

LEG_WITHDRAWAL = "withdrawal"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@router.post(
    "/admin/withdrawals",
    response_model=WithdrawalResponseDTO,
    response_model_exclude_none=True,
    status_code=200,
    summary="Admin cash withdrawal",
    description="Debits an account synchronously; FX applied when needed, waiter on withdrawal-status. "
    "Can decline on insufficient funds, exactly like an ATM.",
)
async def create_withdrawal(
    body: WithdrawalRequestDTO,
    account_repository: AccountRepositoryDep,
    publisher: PublisherDep,
    settings: SettingsDep,
    foreign_exchange_cache_service: ForeignExchangeCacheServiceDep,
    registry: WithdrawalStatusRegistryDep,
    claims: WriteAdminDep,
):
    account = await account_repository.get_by_account_number(body.account_number)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")

    # FX
    if body.currency == account.currency:
        amount_applied = body.amount
        applied_rate = None
    else:
        rates = await foreign_exchange_cache_service.get_rates()
        quote = convert(body.amount, body.currency, account.currency, "debit", rates)
        amount_applied = quote["final_amount"]
        applied_rate = quote["applied_rate"]

    request_id = str(uuid.uuid4())
    # Register waiter before publish to avoid race
    wait_task = asyncio.create_task(registry.wait_for(request_id, timeout=120.0))

    event = {
        "type": "withdrawal",
        "request_id": request_id,
        "account_id": body.account_number,
        "amount": body.amount,
        "currency": body.currency,
        "amount_applied": amount_applied,
        "applied_rate": applied_rate,
        "admin_id": claims.get("sub", ""),
        "leg": LEG_WITHDRAWAL,
        "ts": _now(),
    }
    if applied_rate is None:
        # omit null per spec — optional but keeps event tidy
        event.pop("applied_rate", None)
    if body.reason is not None:
        event["reason"] = body.reason

    publisher.publish(topic=settings.account_events_topic, key=body.account_number, value=event)

    result = await wait_task
    if result is None:
        raise HTTPException(status_code=504, detail="withdrawal confirmation timeout")

    if result.get("status") == "approved":
        return WithdrawalResponseDTO(
            request_id=request_id,
            approved=True,
            amount_applied=result.get("amount_applied", amount_applied),
            applied_rate=result.get("applied_rate", applied_rate),
            new_balance=result["new_balance"],
        )

    return WithdrawalResponseDTO(
        request_id=request_id,
        approved=False,
        reason=result.get("reason", "declined"),
    )
