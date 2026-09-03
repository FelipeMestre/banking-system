"""RED for FX-17: `TransferService.request_transfer` conversion resolution.

Real `conversion_service.convert()` (no mock); fake account repository,
publisher, and foreign exchange cache service — matching this repo's own
"mocking the database is an anti-pattern" convention (`AGENTS.MD`).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, Optional

from openbankapi.config import Settings
from openbankapi.domain.model import Account, AccountStatus
from openbankapi.domain.service.transfer_service import TransferService
from openbankapi.tests.fakes import FakeAccountRepository, FakePublisher

SOURCE = "1234567890123456"
DEST = "6543210987654321"
RATES = {"EUR": 0.8613, "GBP": 0.74}


class SpyForeignExchangeCacheService:
    def __init__(self, rates: Optional[Dict[str, float]] = None):
        self.rates = rates if rates is not None else RATES
        self.calls = 0

    async def get_rates(self) -> Dict[str, float]:
        self.calls += 1
        return dict(self.rates)


def _account(number: str, currency: str) -> Account:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return Account(
        id=uuid.uuid4(), account_number=number, currency=currency,
        customer_id=uuid.uuid4(), branch_id=uuid.uuid4(), balance=0,
        status=AccountStatus.ACTIVE, created_at=now, updated_at=now,
    )


def _service(accounts: FakeAccountRepository, cache: SpyForeignExchangeCacheService):
    settings = Settings(fee_flat_cents=25)
    publisher = FakePublisher()
    service = TransferService(settings, publisher, accounts, cache)
    return service, publisher


def _run(coro):
    return asyncio.run(coro)


# --- same currency: unchanged behavior ---------------------------------------


def test_same_currency_transfer_adds_no_conversion_fields():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "USD")
    accounts.rows[DEST] = _account(DEST, "USD")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    event = _run(service.request_transfer(SOURCE, DEST, 1100))

    assert cache.calls == 0
    _topic, _key, wire = publisher.published[0]
    assert wire["applied_rate"] is None
    assert wire["fee_applied_rate"] is None
    assert wire["destination_amount"] == 1100
    assert wire["fee_amount_usd"] == event.fee_amount


def test_unknown_accounts_leave_the_event_shape_unchanged():
    """Regression guard: v1 callers never created accounts up front."""
    accounts = FakeAccountRepository()
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    _run(service.request_transfer(SOURCE, DEST, 1100))

    assert cache.calls == 0
    _topic, _key, wire = publisher.published[0]
    assert set(wire) == {
        "type", "request_id", "source_account", "destination_account",
        "fees_account", "amount", "fee_amount", "ts",
    }


# --- EUR -> USD: both legs convert --------------------------------------------


def test_eur_to_usd_converts_destination_with_credit_and_fee_with_debit():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "EUR")
    accounts.rows[DEST] = _account(DEST, "USD")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    _run(service.request_transfer(SOURCE, DEST, 1100))

    assert cache.calls == 1, "rates must be fetched exactly once, shared by both legs"
    _topic, _key, wire = publisher.published[0]
    assert wire["applied_rate"]["direction"] == "credit"
    assert wire["fee_applied_rate"]["direction"] == "debit"
    assert wire["destination_amount"] != wire["amount"]
    assert wire["fee_amount_usd"] != wire["fee_amount"]


# --- EUR -> GBP: neither is USD, both convert ---------------------------------


def test_eur_to_gbp_converts_destination_eur_gbp_and_fee_eur_usd():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "EUR")
    accounts.rows[DEST] = _account(DEST, "GBP")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    _run(service.request_transfer(SOURCE, DEST, 1100))

    assert cache.calls == 1
    _topic, _key, wire = publisher.published[0]
    assert wire["applied_rate"]["pair"] == "EUR_GBP"
    assert wire["fee_applied_rate"]["pair"] == "EUR_USD"


# --- destination already USD, fee still converts ------------------------------


def test_eur_to_usd_destination_needs_no_conversion_but_fee_still_does():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "EUR")
    accounts.rows[DEST] = _account(DEST, "USD")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    _run(service.request_transfer(SOURCE, DEST, 1100))

    _topic, _key, wire = publisher.published[0]
    # EUR != USD on both sides, so both flags are true even though the
    # destination happens to already be USD.
    assert wire["applied_rate"] is not None
    assert wire["fee_applied_rate"] is not None


# --- USD -> EUR: no fee conversion needed -------------------------------------


def test_usd_to_eur_converts_destination_only_fee_unconverted():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "USD")
    accounts.rows[DEST] = _account(DEST, "EUR")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    event = _run(service.request_transfer(SOURCE, DEST, 1100))

    _topic, _key, wire = publisher.published[0]
    assert wire["applied_rate"] is not None
    assert wire["fee_applied_rate"] is None
    assert wire["fee_amount_usd"] == event.fee_amount


# --- amount field/existing behavior untouched --------------------------------


def test_amount_and_fee_amount_stay_source_currency_and_unchanged():
    accounts = FakeAccountRepository()
    accounts.rows[SOURCE] = _account(SOURCE, "EUR")
    accounts.rows[DEST] = _account(DEST, "USD")
    cache = SpyForeignExchangeCacheService()
    service, publisher = _service(accounts, cache)

    event = _run(service.request_transfer(SOURCE, DEST, 1100))

    _topic, _key, wire = publisher.published[0]
    assert wire["amount"] == 1100 == event.amount
    assert wire["fee_amount"] == event.fee_amount
