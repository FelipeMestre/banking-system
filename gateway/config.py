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
    transfer_status_topic: str = "transfer-status"

    # The third account of the book's algorithm: where the fee is credited.
    fees_account: str = "acc-fees"

    # Flat fee in integer cents. The spec leaves the fee model open (§6);
    # a flat fee keeps every amount exact with no rounding rules to argue about,
    # and 25 reproduces the worked example in §4.
    fee_flat_cents: int = 25

    cors_allow_origins: Tuple[str, ...] = ("http://localhost:3000",)

    # How long a WebSocket waits for a verdict before answering "pending" and
    # closing, so an unanswered request cannot pin a connection forever.
    websocket_timeout_seconds: float = 30.0

    status_cache_size: int = 10_000

    # Empty means "generate a unique group per process". Every gateway instance
    # has to see every partition of transfer-status, otherwise a socket waiting
    # on one instance would never be told about a verdict that landed on
    # another. A shared group id would split those partitions between instances.
    status_consumer_group: str = ""

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
            account_events_topic=os.getenv("ACCOUNT_EVENTS_TOPIC", "account-events"),
            transfer_status_topic=os.getenv("TRANSFER_STATUS_TOPIC", "transfer-status"),
            fees_account=os.getenv("FEES_ACCOUNT", "acc-fees"),
            fee_flat_cents=int(os.getenv("FEE_FLAT_CENTS", "25")),
            cors_allow_origins=_tuple_from_env(
                "CORS_ALLOW_ORIGINS", ("http://localhost:3000",)
            ),
            websocket_timeout_seconds=float(os.getenv("WEBSOCKET_TIMEOUT_SECONDS", "30")),
            status_cache_size=int(os.getenv("STATUS_CACHE_SIZE", "10000")),
            status_consumer_group=os.getenv("STATUS_CONSUMER_GROUP", ""),
        )
