"""RED for TransactionConsumer withdrawal routing — mirrors
test_transaction_consumer_deposit.py, plus the declined_withdrawal case
deposit never needed."""

import asyncio
import json
import uuid

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer
from openbankapi.tests.fakes import FakeAppliedRateRepository, FakeTransactionRepository


class FakeWithdrawalRepository:
    def __init__(self):
        self.rows = []
        self.inserts = []

    async def insert(self, *, movement_id, admin_id, reason=None):
        # Simulate ON CONFLICT DO NOTHING on movement_id
        if any(r["movement_id"] == movement_id for r in self.rows):
            return
        self.rows.append(
            {"movement_id": movement_id, "admin_id": admin_id, "reason": reason}
        )
        self.inserts.append(movement_id)


def _withdrawal_confirmed_event(
    request_id,
    amount=45540,
    currency="EUR",
    applied_rate=None,
    admin_id="admin-42",
    reason="atm withdrawal",
    account_id="1234567890123456",
):
    payload = {
        "type": "withdrawal_confirmed",
        "request_id": request_id,
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "leg": "withdrawal",
        "admin_id": admin_id,
        "reason": reason,
        "ts": "2026-09-09T12:00:00Z",
    }
    if applied_rate is not None:
        payload["applied_rate"] = applied_rate
    return json.dumps(payload).encode()


def _declined_withdrawal_event(request_id, amount=200000, reason="insufficient_funds"):
    payload = {
        "type": "declined_withdrawal",
        "request_id": request_id,
        "account_id": "1234567890123456",
        "amount": amount,
        "reason": reason,
        "ts": "2026-09-09T12:00:00Z",
    }
    return json.dumps(payload).encode()


def test_withdrawal_same_currency_creates_transaction_and_withdrawal():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        withdrawal_repo = FakeWithdrawalRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            withdrawal_repository=withdrawal_repo,
        )
        rid = str(uuid.uuid4())
        await consumer._apply(
            _withdrawal_confirmed_event(rid, amount=45540, currency="EUR", applied_rate=None)
        )
        assert len(tx_repo.rows) == 1
        row = tx_repo.rows[0]
        assert row.type.value == "withdrawal"
        assert row.amount == 45540
        assert row.counterparty_account is None
        assert len(withdrawal_repo.rows) == 1
        assert withdrawal_repo.rows[0]["admin_id"] == "admin-42"
        assert len(rate_repo.rows) == 0

    asyncio.run(scenario())


def test_withdrawal_cross_currency_links_applied_rate():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        withdrawal_repo = FakeWithdrawalRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            withdrawal_repository=withdrawal_repo,
        )
        applied_rate = {
            "pair": "USD_EUR",
            "mid_rate": 0.92,
            "applied_rate": 0.9108,
            "margin": 0.01,
            "direction": "debit",
            "source_ts": "2026-09-09T12:00:00+00:00",
        }
        rid = str(uuid.uuid4())
        await consumer._apply(
            _withdrawal_confirmed_event(rid, amount=45540, currency="EUR", applied_rate=applied_rate)
        )
        assert len(tx_repo.rows) == 1
        assert len(rate_repo.rows) == 1
        assert tx_repo.rows[0].applied_rate_id == rate_repo.rows[0]["id"]
        assert len(withdrawal_repo.rows) == 1

    asyncio.run(scenario())


def test_withdrawal_duplicate_on_conflict_returns_none():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        withdrawal_repo = FakeWithdrawalRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            withdrawal_repository=withdrawal_repo,
        )
        rid = "22222222-2222-2222-2222-222222222222"
        payload = _withdrawal_confirmed_event(rid, amount=45540)
        await consumer._apply(payload)
        await consumer._apply(payload)
        assert len(tx_repo.rows) == 1
        assert len(withdrawal_repo.rows) == 1
        assert len(rate_repo.rows) == 0

    asyncio.run(scenario())


def test_declined_withdrawal_has_no_destination_account():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        consumer = TransactionConsumer(Settings(), tx_repo)
        rid = str(uuid.uuid4())
        await consumer._apply(_declined_withdrawal_event(rid, amount=200000))
        assert len(tx_repo.rows) == 1
        row = tx_repo.rows[0]
        assert row.type.value == "declined"
        assert row.counterparty_account is None
        assert row.decline_reason == "insufficient_funds"

    asyncio.run(scenario())
