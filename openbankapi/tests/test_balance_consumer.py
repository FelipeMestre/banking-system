"""The account-balances read-model sync (spec §3.6).

Exercises `_apply` and `_parse` directly rather than spinning a Kafka consumer:
the thread and the poll loop are plumbing, the projection logic is the part
that can be wrong.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from openbankapi.config import Settings
from openbankapi.domain.events import BalanceUpdated
from openbankapi.infra.kafka.services import AccountBalanceConsumer

from .fakes import FakeCache, FakeAccountRepository

ACCOUNT_NUMBER = "1234567890123456"


def _consumer(repo, cache):
    return AccountBalanceConsumer(Settings(), repo, cache)


async def _seeded_repo():
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    repo = FakeAccountRepository(known_customers={customer_id}, known_branches={branch_id})
    account = await repo.create(currency="USD", customer_id=customer_id, branch_id=branch_id)
    return repo, account.account_number


# --- parsing ----------------------------------------------------------------


def test_a_well_formed_record_parses():
    event = BalanceUpdated.from_payload({"account_id": ACCOUNT_NUMBER, "balance": 458700, "ts": "t"})
    assert (event.account_id, event.balance) == (ACCOUNT_NUMBER, 458700)


@pytest.mark.parametrize("payload", [
    {"account_id": ACCOUNT_NUMBER},
    {"balance": 10},
    {"account_id": 123, "balance": 10},
    {"account_id": ACCOUNT_NUMBER, "balance": "lots"},
])
def test_a_malformed_record_is_rejected(payload):
    with pytest.raises((ValueError, KeyError)):
        BalanceUpdated.from_payload(payload)


def test_a_malformed_record_is_dropped_not_fatal():
    """One poison message must not kill the consumer."""
    assert AccountBalanceConsumer._parse(json.dumps({"nope": 1}).encode()) is None
    assert AccountBalanceConsumer._parse(b"not json") is None
    assert AccountBalanceConsumer._parse(b"") is None


# --- projection -------------------------------------------------------------


def test_it_updates_balance_and_invalidates_the_cache():
    async def scenario():
        repo, numero = await _seeded_repo()
        cache = FakeCache()
        cache.store[f"account:{numero}"] = {"balance": 0}

        await _consumer(repo, cache)._apply(BalanceUpdated(numero, 458700, "t"))
        return numero, repo.rows[numero].balance, cache.deletes, cache.store

    numero, balance, deletes, store = asyncio.run(scenario())
    assert balance == 458700
    assert deletes == [f"account:{numero}"]
    assert f"account:{numero}" not in store, "the stale entry must be gone"


def test_an_unknown_account_is_skipped_without_raising():
    """The ledger runs accounts reference data has never heard of."""
    async def scenario():
        cache = FakeCache()
        await _consumer(FakeAccountRepository(), cache)._apply(
            BalanceUpdated("9999999999999999", 100, "t")
        )
        return cache.deletes

    # No exception, and no invalidation for a row that does not exist.
    assert asyncio.run(scenario()) == []


def test_replaying_the_same_record_converges():
    """The topic is compacted; re-applying a snapshot is idempotent."""
    async def scenario():
        repo, numero = await _seeded_repo()
        consumer = _consumer(repo, FakeCache())
        for _ in range(3):
            await consumer._apply(BalanceUpdated(numero, 12345, "t"))
        return repo.rows[numero].balance

    assert asyncio.run(scenario()) == 12345


def test_the_projection_is_the_only_thing_that_writes_balance():
    """A CRUD update must not be able to move the balance, even internally."""
    async def scenario():
        repo, numero = await _seeded_repo()
        await _consumer(repo, FakeCache())._apply(BalanceUpdated(numero, 500, "t"))
        await repo.update(numero, status="blocked")
        return repo.rows[numero].balance

    assert asyncio.run(scenario()) == 500
