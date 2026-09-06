"""RED/GREEN for task D1: new `Settings` fields for the monthly batch,
sourced via `from_env()` per the `fee_flat_cents` precedent."""
from __future__ import annotations

import os
from decimal import Decimal

from openbankapi.config.config import Settings


def test_from_env_uses_defaults_when_unset(monkeypatch):
    for name in (
        "CREDIT_CARD_APR", "LATE_FEE_AMOUNT", "CLOSE_DAY",
        "DUE_DATE_OFFSET_DAYS", "MINIMUM_PAYMENT_RATE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.credit_card_apr == Decimal("0.24")
    assert settings.late_fee_amount == Decimal("35.00")
    assert settings.close_day == 20
    assert settings.due_date_offset_days == 20
    assert settings.minimum_payment_rate == Decimal("0.02")


def test_from_env_reads_overridden_values(monkeypatch):
    monkeypatch.setenv("CREDIT_CARD_APR", "0.18")
    monkeypatch.setenv("LATE_FEE_AMOUNT", "8.00")
    monkeypatch.setenv("CLOSE_DAY", "5")
    monkeypatch.setenv("DUE_DATE_OFFSET_DAYS", "25")
    monkeypatch.setenv("MINIMUM_PAYMENT_RATE", "0.03")

    settings = Settings.from_env()

    assert settings.credit_card_apr == Decimal("0.18")
    assert settings.late_fee_amount == Decimal("8.00")
    assert settings.close_day == 5
    assert settings.due_date_offset_days == 25
    assert settings.minimum_payment_rate == Decimal("0.03")
