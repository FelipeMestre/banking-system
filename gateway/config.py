"""Gateway configuration (spec §6)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple


def _tuple_from_env(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    bootstrap_servers: str = "kafka:19092"
    account_events_topic: str = "account-events"

    # The third account of the book's algorithm: where the fee is credited.
    fees_account: str = "acc-fees"

    # Flat fee in integer cents. The spec leaves the fee model open (§6);
    # a flat fee keeps every amount exact with no rounding rules to argue about,
    # and 25 reproduces the worked example in §4.
    fee_flat_cents: int = 25

    cors_allow_origins: Tuple[str, ...] = ("http://localhost:3000",)

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
            account_events_topic=os.getenv("ACCOUNT_EVENTS_TOPIC", "account-events"),
            fees_account=os.getenv("FEES_ACCOUNT", "acc-fees"),
            fee_flat_cents=int(os.getenv("FEE_FLAT_CENTS", "25")),
            cors_allow_origins=_tuple_from_env(
                "CORS_ALLOW_ORIGINS", ("http://localhost:3000",)
            ),
        )
