"""RED for CardBalanceConsumer projection (task 4.1)."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from openbankapi.config import Settings
from openbankapi.domain.events.card_balance_updated import CardBalanceUpdated
from openbankapi.infra.kafka.consumers.card_balance_consumer import CardBalanceConsumer

from .fakes import FakeCache, FakeCardAccountRepository


def _consumer(repo, cache):
    return CardBalanceConsumer(Settings(), repo, cache)


async def _seeded_repo():
    customer_id, branch_id = uuid.uuid4(), uuid.uuid4()
    repo = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={branch_id})
    # need paying account id: we use branch_id as proxy for account id? Fake needs known_accounts set to contain paying_account_id
    # Create via repo.create
    account = await repo.create(customer_id=customer_id, paying_account_id=branch_id, credit_limit=100000)
    return repo, account.id


def test_parse_valid_and_negative():
    event = CardBalanceUpdated.from_payload({"card_account_id": str(uuid.uuid4()), "used_credit": 30000, "ts": "t"})
    assert event.used_credit == 30000
    neg = CardBalanceUpdated.from_payload({"card_account_id": str(uuid.uuid4()), "used_credit": -5000, "ts": "t"})
    assert neg.used_credit == -5000


def test_parse_malformed_dropped():
    assert CardBalanceConsumer._parse(b"not json") is None
    assert CardBalanceConsumer._parse(b"") is None
    assert CardBalanceConsumer._parse(json.dumps({"card_account_id": 123, "used_credit": "lots"}).encode()) is None
    assert CardBalanceConsumer._parse(json.dumps({"card_account_id": str(uuid.uuid4())}).encode()) is None


def test_valid_projects_and_invalidates_after_write():
    async def scenario():
        repo, card_account_id = await _seeded_repo()
        cache = FakeCache()
        cache.store[f"card_account:{card_account_id}"] = {"used_credit": 0}
        consumer = _consumer(repo, cache)
        await consumer._apply(CardBalanceUpdated(str(card_account_id), 30000, "t"))
        return card_account_id, repo.rows[card_account_id].used_credit, cache.deletes, cache.store

    card_account_id, balance, deletes, store = asyncio.run(scenario())
    assert balance == 30000
    assert deletes == [f"card_account:{card_account_id}"]
    assert f"card_account:{card_account_id}" not in store


def test_poison_and_unknown_skipped():
    async def scenario():
        cache = FakeCache()
        # unknown id should return False and not delete
        consumer = _consumer(FakeCardAccountRepository(), cache)
        result = await consumer._apply(CardBalanceUpdated(str(uuid.uuid4()), 5000, "t"))
        return result, cache.deletes

    result, deletes = asyncio.run(scenario())
    assert result is False
    assert deletes == []


def test_replay_converges():
    async def scenario():
        repo, card_account_id = await _seeded_repo()
        consumer = _consumer(repo, FakeCache())
        for _ in range(3):
            await consumer._apply(CardBalanceUpdated(str(card_account_id), 12345, "t"))
        return repo.rows[card_account_id].used_credit

    assert asyncio.run(scenario()) == 12345


def test_consumer_config():
    # Check consumer uses correct group, earliest, no auto commit, poll 0.5, daemon, timeout 30s
    source = open("openbankapi/infra/kafka/consumers/card_balance_consumer.py").read()
    config_source = open("openbankapi/config/config.py").read()
    assert "openbankapi-card-balances" in source or "openbankapi-card-balances" in config_source
    assert '"auto.offset.reset": "earliest"' in source or "'auto.offset.reset': 'earliest'" in source
    assert '"enable.auto.commit": False' in source or "'enable.auto.commit': False" in source
    assert "poll(0.5)" in source
    assert "daemon=True" in source
    assert "30" in source  # timeout 30s
    # check cache.delete after write only if updated
    assert "cache.delete" in source
    assert "cache_key(\"card_account\"" in source or "cache_key('card_account'" in source
    # check projection method
    assert "apply_used_credit" in source
    # check Settings defaults
    from openbankapi.config import Settings
    s = Settings()
    assert s.card_balances_topic == "card-balances"
    assert s.card_balance_consumer_group == "openbankapi-card-balances"
