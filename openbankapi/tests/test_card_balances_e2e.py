"""E2E for card-balances projection (task 5.1) — S11 and basic flows.

Exercises the full chain: CardState -> decide -> CardBalanceConsumer -> DTO -> GET.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import importlib.util
from pathlib import Path

_card_domain_path = Path(__file__).resolve().parents[2] / "card-service" / "domain.py"
_spec = importlib.util.spec_from_file_location("card_domain_e2e", _card_domain_path)
_domain_mod = importlib.util.module_from_spec(_spec)
import sys
sys.modules["card_domain_e2e"] = _domain_mod
_spec.loader.exec_module(_domain_mod)
domain = _domain_mod  # type: ignore

from openbankapi.domain.events.card_balance_updated import CardBalanceUpdated
from openbankapi.infra.kafka.consumers.card_balance_consumer import CardBalanceConsumer
from openbankapi.config import Settings
from openbankapi.tests.fakes import FakeCache, FakeCardAccountRepository
from openbankapi.api.v1.dtos.card_account_dto import CardAccountResponseDTO

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


def test_purchase_300_cents_to_30000_and_payment_100_to_20000():
    async def scenario():
        customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account_id})
        cache = FakeCache()
        card_account = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=100000)
        # Simulate Flink approval: purchase 30000
        decision = domain.decide(domain.CardState(used_credit=0), {"type": "purchase_requested", "request_id": "r1", "card_id": "c1", "card_account_id": str(card_account.id), "amount_usd": 30000, "credit_limit": 100000}, NOW)
        assert decision.card_balance_events[0]["used_credit"] == 30000
        consumer = CardBalanceConsumer(Settings(), repo, cache)
        await consumer._apply(CardBalanceUpdated(str(card_account.id), decision.card_balance_events[0]["used_credit"], NOW.isoformat()))
        fetched = await repo.get_by_id(card_account.id)
        assert fetched.used_credit == 30000
        # DTO should surface it
        dto = CardAccountResponseDTO.model_validate(fetched)
        assert dto.used_credit == 30000

        # Payment 10000 -> 20000
        decision2 = domain.decide(domain.CardState(used_credit=30000), {"type": "card_payment_received", "request_id": "p1", "card_id": "c1", "card_account_id": str(card_account.id), "amount_usd": 10000}, NOW)
        assert decision2.card_balance_events[0]["used_credit"] == 20000
        await consumer._apply(CardBalanceUpdated(str(card_account.id), decision2.card_balance_events[0]["used_credit"], NOW.isoformat()))
        fetched2 = await repo.get_by_id(card_account.id)
        assert fetched2.used_credit == 20000
        dto2 = CardAccountResponseDTO.model_validate(fetched2)
        assert dto2.used_credit == 20000

    asyncio.run(scenario())


def test_decline_leaves_20000_and_overpayment_negative():
    async def scenario():
        customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account_id})
        cache = FakeCache()
        card_account = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=100000)
        repo.rows[card_account.id] = type(repo.rows[card_account.id])(**{**repo.rows[card_account.id].__dict__, "used_credit": 20000})
        consumer = CardBalanceConsumer(Settings(), repo, cache)
        # Decline: should emit nothing, so no _apply; balance stays 20000
        decision = domain.decide(domain.CardState(used_credit=20000), {"type": "purchase_requested", "request_id": "r2", "card_id": "c1", "card_account_id": str(card_account.id), "amount_usd": 90000, "credit_limit": 100000}, NOW)
        assert decision.card_balance_events == ()
        fetched = await repo.get_by_id(card_account.id)
        assert fetched.used_credit == 20000

        # Overpayment: used_credit 10000 payment 20000 -> -10000
        repo2 = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account_id})
        ca2 = await repo2.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=100000)
        repo2.rows[ca2.id] = type(ca2)(**{**repo2.rows[ca2.id].__dict__, "used_credit": 10000})
        decision2 = domain.decide(domain.CardState(used_credit=10000), {"type": "card_payment_received", "request_id": "p2", "card_id": "c1", "card_account_id": str(ca2.id), "amount_usd": 20000}, NOW)
        assert decision2.card_balance_events[0]["used_credit"] == -10000
        consumer2 = CardBalanceConsumer(Settings(), repo2, cache)
        await consumer2._apply(CardBalanceUpdated(str(ca2.id), -10000, NOW.isoformat()))
        fetched2 = await repo2.get_by_id(ca2.id)
        assert fetched2.used_credit == -10000

    asyncio.run(scenario())


def test_s11_limit_raise_uses_fresh_limit():
    # GIVEN used_credit 90000 limit 100000 then PUT raises to 200000 before purchase 50000
    # WHEN Flink evaluates available = 200000 - 90000 fresh credit_limit from event
    # THEN approved and GET shows 140000
    decision = domain.decide(domain.CardState(used_credit=90000), {"type": "purchase_requested", "request_id": "r3", "card_id": "c1", "card_account_id": "acct-1", "amount_usd": 50000, "credit_limit": 200000}, NOW)
    assert decision.new_used_credit == 140000
    assert decision.card_balance_events[0]["used_credit"] == 140000
    assert decision.card_events[0]["type"] == "purchase_approved"

    async def via_repo():
        customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account_id})
        cache = FakeCache()
        ca = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=100000)
        # set used_credit to 90000 via projection
        await repo.apply_used_credit(ca.id, 90000)
        # simulate limit raise via PUT (repo.update_limit)
        await repo.update_limit(ca.id, credit_limit=200000)
        # Flink sees fresh limit 200000
        dec = domain.decide(domain.CardState(used_credit=90000), {"type": "purchase_requested", "request_id": "r4", "card_id": "c1", "card_account_id": str(ca.id), "amount_usd": 50000, "credit_limit": 200000}, NOW)
        consumer = CardBalanceConsumer(Settings(), repo, cache)
        await consumer._apply(CardBalanceUpdated(str(ca.id), dec.card_balance_events[0]["used_credit"], NOW.isoformat()))
        fetched = await repo.get_by_id(ca.id)
        assert fetched.used_credit == 140000
        dto = CardAccountResponseDTO.model_validate(fetched)
        assert dto.used_credit == 140000

    asyncio.run(via_repo())


def test_get_cards_and_list():
    from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO, CardMaskedDTO
    # GET /cards must not have used_credit
    for cls in (CardIssuedDTO, CardMaskedDTO):
        assert "used_credit" not in cls.model_fields

    async def scenario():
        customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account_id})
        cache = FakeCache()
        ca1 = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=100000)
        ca2 = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=200000)
        await repo.apply_used_credit(ca1.id, 30000)
        await repo.apply_used_credit(ca2.id, 50000)
        page = await repo.list_by_customer(customer_id, limit=10, offset=0)
        for item in page.items:
            dto = CardAccountResponseDTO.model_validate(item)
            assert hasattr(dto, "used_credit")
            assert dto.used_credit in (30000, 50000)

    asyncio.run(scenario())
