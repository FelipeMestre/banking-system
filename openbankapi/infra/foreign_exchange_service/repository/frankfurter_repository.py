"""Frankfurter integration — FX-3.

Only knows HTTP. No cache, no Redis.
"""

from __future__ import annotations

import httpx

from openbankapi.domain.exceptions import RateNotAvailableError
from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
    ForeignExchangeConfig,
)


class FrankfurterRepository:
    """Fetches mid rates from Frankfurter v2 array API."""

    def __init__(self, config: ForeignExchangeConfig) -> None:
        self._config = config

    async def get_all_mid_rates(self) -> dict[str, float]:
        params = {"base": "USD", "quotes": ",".join(self._config.tracked_currencies)}
        async with httpx.AsyncClient(timeout=self._config.request_timeout_seconds) as client:
            response = await client.get(self._config.base_url, params=params)
            response.raise_for_status()
            rows = response.json()
            rates: dict[str, float] = {}
            for row in rows:
                quote = row.get("quote")
                if quote == "USD":
                    continue
                rate = row.get("rate")
                if quote is not None and rate is not None:
                    rates[str(quote)] = float(rate)
            if not rates:
                raise RateNotAvailableError("Frankfurter returned no usable rates")
            return rates
