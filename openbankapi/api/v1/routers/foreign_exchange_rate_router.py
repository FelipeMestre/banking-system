"""Thin router for foreign exchange display rates (FX-7) and margin-adjusted quotes (FX-13).

Only margin + shaping. No Redis, no HTTP, no TTL. `POST /quote` never writes
an applied-rate audit row — this phase only builds that repository, it does
not wire it into a route (FX-14/FX-15 scope guard).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from openbankapi.config.dependencies import require_permissions

ReadAdminDep = Annotated[dict, Depends(require_permissions("read:admin"))]
WriteAdminDep = Annotated[dict, Depends(require_permissions("write:admin"))]
from openbankapi.api.v1.dtos.foreign_exchange_quote_dto import (
    ForeignExchangeQuoteRequestDTO,
    ForeignExchangeQuoteResponseDTO,
)
from openbankapi.domain.exceptions import RateNotAvailableError
from openbankapi.domain.service import conversion_service

router = APIRouter(tags=["foreign-exchange"])

MARGIN: float = 0.01


@router.get("/foreign-exchange-rates")
async def get_foreign_exchange_rates(request: Request, _claims: ReadAdminDep):
    cache_service = request.app.state.foreign_exchange_cache_service
    rates = await cache_service.get_rates()
    result: list[dict[str, object]] = []
    for currency, mid in rates.items():
        result.append(
            {
                "pair": f"USD_{currency}",
                "display_buy": float(mid) * (1 - MARGIN),
                "display_sell": float(mid) * (1 + MARGIN),
            }
        )
    return {"rates": result}


@router.post("/foreign-exchange-rates/quote", response_model=ForeignExchangeQuoteResponseDTO)
async def quote_conversion(
    payload: ForeignExchangeQuoteRequestDTO, request: Request, _claims: WriteAdminDep
):
    # `payload` validation (amount > 0, a known `customer_effect` literal)
    # already raised a 422 via FastAPI before this body ever runs — no await
    # has happened yet at that point.
    cache_service = request.app.state.foreign_exchange_cache_service
    try:
        rates = await cache_service.get_rates()
    except RateNotAvailableError as error:
        # Local catch only: the global `DomainError`->502 mapping in
        # error_handlers.py stays untouched for every other route.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    result = conversion_service.convert(
        payload.amount,
        payload.from_currency,
        payload.to_currency,
        payload.customer_effect,
        rates,
    )
    applied_rate = result["applied_rate"]
    return ForeignExchangeQuoteResponseDTO(
        final_amount=result["final_amount"],
        from_currency=payload.from_currency,
        to_currency=payload.to_currency,
        applied_rate=applied_rate["applied_rate"] if applied_rate is not None else None,
    )
