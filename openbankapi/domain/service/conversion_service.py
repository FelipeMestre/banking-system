"""Pure margin-adjusted conversion quote math (FX-12).

Zero I/O, zero imports from `api`/`infra` — only `RateNotAvailableError` from
this same domain layer. `rates` is the flat `dict[str, float]` shape
`ForeignExchangeCacheService.get_rates()` already returns: currency code ->
"1 USD = N units of that currency". `now` is injectable only so a caller can
get a deterministic `source_ts` in tests; production code never passes it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional, TypedDict

from ..exceptions import RateNotAvailableError

MARGIN: float = 0.01


class AppliedRate(TypedDict):
    pair: str
    mid_rate: float
    applied_rate: float
    margin: float
    direction: Literal["credit", "debit"]
    source_ts: str


class ConversionQuote(TypedDict):
    final_amount: int
    applied_rate: Optional[AppliedRate]


def _rate_for(currency: str, rates: dict[str, float]) -> float:
    try:
        return rates[currency]
    except KeyError as error:
        raise RateNotAvailableError(f"no rate available for {currency}") from error


def get_mid_rate(from_currency: str, to_currency: str, rates: dict[str, float]) -> float:
    """USD->X: `rates[X]`; X->USD: `1/rates[X]`; X->Y (neither USD): `(1/rates[X])*rates[Y]`.

    Same-currency always returns 1.0. Raises `RateNotAvailableError` when a
    required currency is missing from `rates`.
    """
    if from_currency == to_currency:
        return 1.0
    if from_currency == "USD":
        return _rate_for(to_currency, rates)
    if to_currency == "USD":
        return 1 / _rate_for(from_currency, rates)
    return (1 / _rate_for(from_currency, rates)) * _rate_for(to_currency, rates)


def convert(
    amount: int,
    from_currency: str,
    to_currency: str,
    customer_effect: Literal["credit", "debit"],
    rates: dict[str, float],
    *,
    now: Optional[datetime] = None,
) -> ConversionQuote:
    """Fair-then-adjust, in this exact order:

    1. `fair_amount = amount * mid_rate`
    2. `adjustment = 1 - MARGIN` (credit) or `1 + MARGIN` (debit)
    3. `final_amount = round(fair_amount * adjustment)`

    Same-currency short-circuits to the amount unchanged, no margin applied.
    """
    if from_currency == to_currency:
        return {"final_amount": amount, "applied_rate": None}

    mid_rate = get_mid_rate(from_currency, to_currency, rates)
    fair_amount = amount * mid_rate
    adjustment = (1 - MARGIN) if customer_effect == "credit" else (1 + MARGIN)
    final_amount = round(fair_amount * adjustment)
    applied_rate = mid_rate * adjustment
    source_ts = now or datetime.now(timezone.utc)

    return {
        "final_amount": final_amount,
        "applied_rate": {
            "pair": f"{from_currency}_{to_currency}",
            "mid_rate": mid_rate,
            "applied_rate": applied_rate,
            "margin": MARGIN,
            "direction": customer_effect,
            "source_ts": source_ts.isoformat(),
        },
    }
