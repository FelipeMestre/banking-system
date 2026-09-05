"""OpenBankAPI configuration (spec §8, §10)."""
from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass
from typing import Tuple

LOG = logging.getLogger("openbankapi.config")


def _tuple_from_env(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    # --- Kafka ---
    bootstrap_servers: str = "kafka:19092"
    account_events_topic: str = "account-events"
    transfer_status_topic: str = "transfer-status"
    account_balances_topic: str = "account-balances"
    status_consumer_group: str = ""          # empty -> unique per process
    balance_consumer_group: str = "openbankapi-balances"
    transaction_consumer_group: str = "openbankapi-transactions"
    card_events_topic: str = "card-events"
    purchase_status_topic: str = "purchase-status"
    card_movement_consumer_group: str = "openbankapi-card-movements"
    purchase_status_consumer_group: str = ""  # empty -> unique per process

    # --- Postgres / Redis ---
    database_dsn: str = "postgresql+asyncpg://openbank:openbank@postgres:5432/openbank"
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_seconds: int = 300

    # --- Payments ---
    # The fees account is now a real 16-digit number: 'acc-fees' would fail the
    # accounts CHECK constraint, and this value is a Kafka partition key.
    fees_account: str = "0000000000000001"
    fee_flat_cents: int = 25

    # --- HTTP ---
    cors_allow_origins: Tuple[str, ...] = ("http://localhost:3000",)
    websocket_timeout_seconds: float = 30.0
    status_cache_size: int = 10_000

    # --- Auth0 ---
    # No client secret here on purpose: verifying an Access Token is a JWKS
    # (public-key) check, not a token exchange — this API is a resource
    # server, not an OAuth client of its own.
    auth0_domain: str = ""
    auth0_audience: str = "https://openbank.api/com/auth"

    @staticmethod
    def from_env() -> "Settings":
        audience = os.getenv("AUTH0_AUDIENCE", "https://openbank.api/com/auth")
        if "api/v2/" in audience:
            warnings.warn(
                "AUTH0_AUDIENCE contains api/v2/ — expected https://openbank.api/com/auth; "
                "tokens with Management API audience will be rejected with 401.",
                UserWarning,
                stacklevel=2,
            )
            LOG.warning("AUTH0_AUDIENCE looks like Management API audience: %s", audience)
        return Settings(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
            account_events_topic=os.getenv("ACCOUNT_EVENTS_TOPIC", "account-events"),
            transfer_status_topic=os.getenv("TRANSFER_STATUS_TOPIC", "transfer-status"),
            account_balances_topic=os.getenv("ACCOUNT_BALANCES_TOPIC", "account-balances"),
            status_consumer_group=os.getenv("STATUS_CONSUMER_GROUP", ""),
            balance_consumer_group=os.getenv("BALANCE_CONSUMER_GROUP", "openbankapi-balances"),
            transaction_consumer_group=os.getenv(
                "TRANSACTION_CONSUMER_GROUP", "openbankapi-transactions"
            ),
            card_events_topic=os.getenv("CARD_EVENTS_TOPIC", "card-events"),
            purchase_status_topic=os.getenv("PURCHASE_STATUS_TOPIC", "purchase-status"),
            card_movement_consumer_group=os.getenv(
                "CARD_MOVEMENT_CONSUMER_GROUP", "openbankapi-card-movements"
            ),
            purchase_status_consumer_group=os.getenv("PURCHASE_STATUS_CONSUMER_GROUP", ""),
            database_dsn=os.getenv(
                "DATABASE_DSN", "postgresql+asyncpg://openbank:openbank@postgres:5432/openbank"
            ),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
            fees_account=os.getenv("FEES_ACCOUNT", "0000000000000001"),
            fee_flat_cents=int(os.getenv("FEE_FLAT_CENTS", "25")),
            cors_allow_origins=_tuple_from_env("CORS_ALLOW_ORIGINS", ("http://localhost:3000",)),
            websocket_timeout_seconds=float(os.getenv("WEBSOCKET_TIMEOUT_SECONDS", "30")),
            status_cache_size=int(os.getenv("STATUS_CACHE_SIZE", "10000")),
            auth0_domain=os.getenv("AUTH0_DOMAIN", ""),
            auth0_audience=audience,
        )
