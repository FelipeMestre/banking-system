"""Shared money-math helpers for the credit-card domain.

Extracted verbatim from `statement_service.py`'s private `_quantize`/`_clamp`
so `current_cycle_projection_service.py` can reuse the exact same rounding
rule without duplicating it (AGENTS.MD DRY convention). This is an
import-only extraction: no logic changed from the original private helpers.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def clamp(value: Decimal, *, low: Decimal, high: Decimal) -> Decimal:
    if value < low:
        return low
    if value > high:
        return high
    return value
