"""Seed opening balances out of band (spec §3.5).

The ledger has no deposit concept: a balance is whatever the account's event log
says. Seeding therefore produces an `incoming_payment` rather than touching
`cuentas.saldo`, which would be a second write path to a fact Flink owns.

    python -m openbankapi.seed 1234567890123456=500000
"""
from __future__ import annotations

import sys

from .config import Settings
from .domain.model import is_valid_numero_cuenta
from .domain.service import CuentaService
from .infra.kafka.adapters import KafkaEventPublisher


def _parse(pair: str):
    account, _, amount = pair.partition("=")
    if not account or not amount:
        raise ValueError(f"expected numero_cuenta=cents, got {pair!r}")
    if not is_valid_numero_cuenta(account):
        raise ValueError(f"numero_cuenta must be 16 digits, got {account!r}")
    return account, int(amount)


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    try:
        openings = [_parse(pair) for pair in argv]
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    settings = Settings.from_env()
    publisher = KafkaEventPublisher(settings)
    service = CuentaService(settings, repository=None, publisher=publisher)

    for account, cents in openings:
        if cents <= 0:
            print(f"skipping {account}: nothing to credit")
            continue
        service.credit_opening_balance(account, cents)
        print(f"seeded {account} with {cents} cents")

    publisher.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
