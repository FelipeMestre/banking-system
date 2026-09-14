"""RED for FX-12: pure conversion domain service — plain dict fixtures, no mocks."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from openbankapi.domain.exceptions import RateNotAvailableError
from openbankapi.domain.service.conversion_service import convert, get_mid_rate

RATES = {"EUR": 0.86, "GBP": 0.74}


def test_same_currency_passthrough():
    result = convert(10000, "EUR", "EUR", "debit", RATES)
    assert result == {"final_amount": 10000, "applied_rate": None}


def test_eur_to_usd_debit_charges_more_than_fair():
    result = convert(10000, "EUR", "USD", "debit", RATES)
    assert result["final_amount"] == 11744


def test_eur_to_usd_credit_pays_less_and_differs_from_debit():
    credit = convert(10000, "EUR", "USD", "credit", RATES)
    debit = convert(10000, "EUR", "USD", "debit", RATES)
    assert credit["final_amount"] == 11512
    assert credit["final_amount"] != debit["final_amount"]


def test_usd_to_eur_debit_charges_more():
    result = convert(10000, "USD", "EUR", "debit", RATES)
    assert result["final_amount"] == 8686


def test_usd_to_eur_credit_pays_less_and_differs_from_debit():
    credit = convert(10000, "USD", "EUR", "credit", RATES)
    debit = convert(10000, "USD", "EUR", "debit", RATES)
    assert credit["final_amount"] == 8514
    assert credit["final_amount"] != debit["final_amount"]


def test_missing_currency_raises_on_convert():
    with pytest.raises(RateNotAvailableError):
        convert(1000, "USD", "GBP", "debit", {"EUR": 0.86})


def test_missing_currency_raises_on_get_mid_rate():
    with pytest.raises(RateNotAvailableError):
        get_mid_rate("USD", "GBP", {"EUR": 0.86})


def test_applied_rate_shape_and_fair_then_adjust_ordering():
    result = convert(10000, "EUR", "USD", "debit", RATES)
    applied = result["applied_rate"]
    mid_rate = get_mid_rate("EUR", "USD", RATES)
    assert applied["pair"] == "EUR_USD"
    assert applied["mid_rate"] == mid_rate
    # fair-then-adjust: applied_rate is mid_rate * adjustment, never a
    # pre-adjusted rate multiplied by amount directly.
    assert applied["applied_rate"] == mid_rate * 1.01
    assert applied["margin"] == 0.01
    assert applied["direction"] == "debit"


def test_injectable_now_produces_exact_source_ts():
    fixed_now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
    result = convert(10000, "EUR", "USD", "debit", RATES, now=fixed_now)
    assert result["applied_rate"]["source_ts"] == fixed_now.isoformat()


def test_get_mid_rate_same_currency():
    assert get_mid_rate("USD", "USD", RATES) == 1.0


def test_get_mid_rate_usd_to_x():
    assert get_mid_rate("USD", "EUR", RATES) == 0.86


def test_get_mid_rate_x_to_usd():
    assert get_mid_rate("EUR", "USD", RATES) == 1 / 0.86


def test_get_mid_rate_cross_pair():
    assert get_mid_rate("EUR", "GBP", RATES) == (1 / 0.86) * 0.74
