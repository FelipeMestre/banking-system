"""Frozen config for the Frankfurter integration (FX-1).

Owns only what the HTTP client needs. No Redis or TTL knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForeignExchangeConfig:
    base_url: str = "https://api.frankfurter.dev/v2/rates"
    tracked_currencies: list[str] = field(default_factory=lambda: ["EUR", "GBP"])
    request_timeout_seconds: float = 10.0
