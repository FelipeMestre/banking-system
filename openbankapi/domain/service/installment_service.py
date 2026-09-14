"""Pure remainder-distribution split for card purchase installments (Phase 2).

Zero I/O — mirrors `conversion_service.py`'s shape. Called by
`card_movement_consumer.py` once a `card_movements` row is persisted (the
split needs the generated `movement_id` as FK, which is a consumer-side
concern, not Flink-job state — design §5).

Algorithm: `base = total // count`, `remainder = total - base * count`. The
FIRST `remainder` installments get `base + 1`, the rest get `base` — not the
LAST installment, per the tasks checklist's explicit note to align with the
worked example ($100.00 / 3 -> 33.34, 33.33, 33.33). This always sums to
exactly `total`.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal

_CENT = Decimal("0.01")


def split_into_installments(total: Decimal, count: int, due_dates: list[date]) -> list[Decimal]:
    """Split `total` into `count` parts (2 decimal places), assigning any
    remainder cents to the first installments so the sum always equals
    `total` exactly."""
    total_cents = int((total / _CENT).to_integral_value(rounding=ROUND_DOWN))
    base_cents, remainder_cents = divmod(total_cents, count)

    amounts_cents = [
        base_cents + 1 if index < remainder_cents else base_cents for index in range(count)
    ]
    return [(Decimal(cents) * _CENT) for cents in amounts_cents]
