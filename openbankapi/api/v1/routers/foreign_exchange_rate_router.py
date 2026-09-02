"""Thin router for FX display rates — FX-7.

Only margin + shaping. No Redis, no HTTP, no TTL.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["foreign-exchange"])

MARGIN: float = 0.01


@router.get("/foreign-exchange-rates")
async def get_foreign_exchange_rates(request: Request):
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
