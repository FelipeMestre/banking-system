"""Cache-aside for FX mid rates — FX-5/FX-6.

Only place that touches foreign_exchange:mid_rate:* keys.
Reuses ICacheService single pool, no second client, no HTTP.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openbankapi.infra.cache.interfaces.cache_service import ICacheService
from openbankapi.infra.foreign_exchange_service.repository.foreign_exchange_repository_interface import (
    IForeignExchangeRepository,
)

TRACKED_CURRENCIES: list[str] = ["EUR", "GBP"]
CACHE_TTL_SECONDS: int = 86400


class ForeignExchangeCacheService:
    """Owns keys, TTL, payload and fetch-once semantics."""

    def __init__(
        self,
        cache: ICacheService | None = None,
        foreign_exchange_repository: IForeignExchangeRepository | None = None,
        *,
        redis_client: ICacheService | None = None,
    ) -> None:
        # Spec literal uses redis_client; idiomatic is cache: ICacheService.
        # Support both without creating a second client.
        resolved_cache = cache if cache is not None else redis_client
        if resolved_cache is None:
            raise TypeError("ForeignExchangeCacheService requires cache / redis_client")
        if foreign_exchange_repository is None:
            raise TypeError("ForeignExchangeCacheService requires foreign_exchange_repository")
        self._cache: ICacheService = resolved_cache
        # alias for spec literal compat
        self._redis: ICacheService = resolved_cache
        self._repository: IForeignExchangeRepository = foreign_exchange_repository

    async def get_rates(self) -> dict[str, float]:
        rates: dict[str, float] = {}
        missing: list[str] = []

        for currency in TRACKED_CURRENCIES:
            cached: Any = await self._cache.get(f"foreign_exchange:mid_rate:USD_{currency}")
            if cached is not None:
                try:
                    if isinstance(cached, str):
                        data = json.loads(cached)
                        if isinstance(data, dict) and "mid_rate" in data:
                            rates[currency] = float(data["mid_rate"])
                        elif isinstance(data, dict):
                            # unexpected shape — treat as miss
                            missing.append(currency)
                            continue
                        else:
                            rates[currency] = float(data)  # type: ignore[arg-type]
                    elif isinstance(cached, dict) and "mid_rate" in cached:
                        rates[currency] = float(cached["mid_rate"])
                    elif isinstance(cached, dict):
                        missing.append(currency)
                        continue
                    elif isinstance(cached, (int, float)):
                        rates[currency] = float(cached)
                    else:
                        missing.append(currency)
                        continue
                except Exception:
                    missing.append(currency)
                    continue
            else:
                missing.append(currency)

        if missing:
            fresh_rates = await self._repository.get_all_mid_rates()
            await self._save_rates(fresh_rates)
            # Preserve already-cached values for current response (EUR reused)
            for cur in missing:
                if cur in fresh_rates:
                    rates[cur] = float(fresh_rates[cur])
            # if fresh missing some tracked currency (should not), that currency stays absent
            # but RateNotAvailableError would have been raised earlier only if fresh empty.
        return rates

    async def _save_rates(self, rates: dict[str, float]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for currency, rate in rates.items():
            payload: dict[str, Any] = {"mid_rate": float(rate), "fetched_at": now}
            # ICacheService.set JSON-encodes dict — pass dict, not pre-encoded string
            await self._cache.set(
                f"foreign_exchange:mid_rate:USD_{currency}",
                payload,
                ttl_seconds=CACHE_TTL_SECONDS,
            )
