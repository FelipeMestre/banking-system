"""Seed opening balances out-of-band (spec §5.3).

The ledger has no "deposit" concept: an account's balance is whatever its event
log says. Seeding therefore reuses the existing `incoming_payment` event rather
than inventing a new event type, each with its own request_id so the dedup guard
treats it as a distinct unit of work.

    python -m gateway.seed acc-123=500000 acc-456=0 acc-fees=0
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

from .config import Settings
from .kafka_config import producer_config

LEG_CREDIT_SEED = "credit:seed"


def _parse(pair: str) -> tuple[str, int]:
    account, _, amount = pair.partition("=")
    if not account or not amount:
        raise ValueError(f"expected account=cents, got {pair!r}")
    return account, int(amount)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    try:
        openings = [_parse(pair) for pair in argv]
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    settings = Settings.from_env()
    producer = Producer(producer_config(settings, client_id="gateway-seed"))
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    for account, cents in openings:
        if cents <= 0:
            print(f"skipping {account}: nothing to credit")
            continue
        event = {
            "type": "incoming_payment",
            "request_id": f"seed-{uuid.uuid4()}",
            "account_id": account,
            "amount": cents,
            "leg": LEG_CREDIT_SEED,
            "ts": now,
        }
        producer.produce(
            settings.account_events_topic,
            key=account.encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        )
        print(f"seeded {account} with {cents} cents")

    producer.flush(10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
