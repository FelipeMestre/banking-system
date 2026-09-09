"""RED for `split_into_installments` (task 1.4): remainder-cents distribution.

Design's worked example: $100.00 (10000 cents) in 3 installments -> first
`remainder` installments get `base+1`, the rest get `base` — 3334, 3333, 3333,
summing to exactly 10000 cents / $100.00.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from openbankapi.domain.service.installment_service import split_into_installments


def _due_dates(count: int) -> list[date]:
    start = date(2026, 10, 1)
    return [start + timedelta(days=30 * i) for i in range(count)]


def test_worked_example_100_dollars_in_3_installments():
    result = split_into_installments(Decimal("100.00"), 3, _due_dates(3))
    assert result == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert sum(result) == Decimal("100.00")


def test_full_amount_evenly_divisible():
    result = split_into_installments(Decimal("900.00"), 9, _due_dates(9))
    assert result == [Decimal("100.00")] * 9
    assert sum(result) == Decimal("900.00")


@pytest.mark.parametrize("count", list(range(1, 25)))
@pytest.mark.parametrize("total", ["0.01", "1.00", "12.34", "999.99", "10000.07"])
def test_sum_always_equals_total_for_any_count_1_to_24(total, count):
    total_decimal = Decimal(total)
    result = split_into_installments(total_decimal, count, _due_dates(count))
    assert len(result) == count
    assert sum(result) == total_decimal
    assert all(amount >= Decimal("0.00") for amount in result)
