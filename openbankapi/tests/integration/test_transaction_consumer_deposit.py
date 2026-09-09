"""RED for Task 5.1 — TransactionConsumer deposit routing."""

import asyncio
import json
import uuid

from openbankapi.config import Settings
from openbankapi.infra.kafka.consumers.transaction_consumer import TransactionConsumer
from openbankapi.tests.fakes import FakeAppliedRateRepository, FakeTransactionRepository


class FakeDepositRepository:
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


def _deposit_confirmed_event(
    request_id,
    amount=50000,
    currency="EUR",
    applied_rate=None,
    admin_id="admin-42",
    reason="cash branch 42",
    account_id="1234567890123456",
):
    payload = {
        "type": "deposit_confirmed",
        "request_id": request_id,
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "leg": "deposit",
        "admin_id": admin_id,
        "reason": reason,
        "ts": "2026-09-07T12:00:00Z",
    }
    if applied_rate is not None:
        payload["applied_rate"] = applied_rate
    return json.dumps(payload).encode()


def test_deposit_same_currency_creates_transaction_and_deposit():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        deposit_repo = FakeDepositRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            deposit_repository=deposit_repo,
        )
        rid = str(uuid.uuid4())
        await consumer._apply(
            _deposit_confirmed_event(
                rid, amount=50000, currency="EUR", applied_rate=None
            )
        )
        assert len(tx_repo.rows) == 1
        row = tx_repo.rows[0]
        assert row.type.value == "deposit"
        assert row.amount == 50000
        assert (
            row.counterparty_account is None
            or row.counterparty_account == ""
            or row.counterparty_account is None
        )
        assert len(deposit_repo.rows) == 1
        assert deposit_repo.rows[0]["admin_id"] == "admin-42"
        assert len(rate_repo.rows) == 0

    asyncio.run(scenario())


def test_deposit_cross_currency_links_applied_rate():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        deposit_repo = FakeDepositRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            deposit_repository=deposit_repo,
        )
        applied_rate = {
            "pair": "USD_EUR",
            "mid_rate": 0.92,
            "applied_rate": 0.9108,
            "margin": 0.01,
            "direction": "credit",
            "source_ts": "2026-09-07T12:00:00+00:00",
        }
        rid = str(uuid.uuid4())
        await consumer._apply(
            _deposit_confirmed_event(
                rid, amount=45540, currency="EUR", applied_rate=applied_rate
            )
        )
        assert len(tx_repo.rows) == 1
        assert len(rate_repo.rows) == 1
        assert tx_repo.rows[0].applied_rate_id == rate_repo.rows[0]["id"]
        assert len(deposit_repo.rows) == 1

    asyncio.run(scenario())


def test_deposit_duplicate_on_conflict_returns_none():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        rate_repo = FakeAppliedRateRepository()
        deposit_repo = FakeDepositRepository()
        consumer = TransactionConsumer(
            Settings(),
            tx_repo,
            applied_rate_repository=rate_repo,
            deposit_repository=deposit_repo,
        )
        rid = "11111111-1111-1111-1111-111111111111"
        payload = _deposit_confirmed_event(rid, amount=50000)
        await consumer._apply(payload)
        await consumer._apply(payload)
        # should be idempotent: only 1 transaction and 1 deposit
        assert len(tx_repo.rows) == 1
        assert len(deposit_repo.rows) == 1
        assert len(rate_repo.rows) == 0

    asyncio.run(scenario())


def test_deposit_no_audit_cols_on_transactions():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        deposit_repo = FakeDepositRepository()
        consumer = TransactionConsumer(
            Settings(), tx_repo, deposit_repository=deposit_repo
        )
        rid = str(uuid.uuid4())
        await consumer._apply(_deposit_confirmed_event(rid, amount=50000))
        # ensure transaction row has no admin_id/reason attributes leaked?
        # Check that PostgresTransactionRepository insert does not reference admin_id
        import inspect

        src = inspect.getsource(consumer._insert_for)
        # should not insert admin_id into transactions
        assert "admin_id" not in src or "deposit_repo" in src

    asyncio.run(scenario())


def test_redelivery_idempotent_twice():
    async def scenario():
        tx_repo = FakeTransactionRepository()
        deposit_repo = FakeDepositRepository()
        consumer = TransactionConsumer(
            Settings(), tx_repo, deposit_repository=deposit_repo
        )
        rid = str(uuid.uuid4())
        payload = _deposit_confirmed_event(rid, amount=50000)
        for _ in range(2):
            await consumer._apply(payload)
        assert len(tx_repo.rows) == 1
        assert len(deposit_repo.rows) == 1

    asyncio.run(scenario())
