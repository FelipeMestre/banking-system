"""Port for Frankfurter — FX-2.

No Redis, no TTL. Pure HTTP abstraction.
"""

from __future__ import annotations

from typing import Protocol


class IForeignExchangeRepository(Protocol):
    async def get_all_mid_rates(self) -> dict[str, float]:
        """Return {currency: mid_rate} for all tracked pairs."""
        ...
