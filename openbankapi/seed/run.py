"""Demo seed for AUTH0_SUB=auth0|6a90f3247c7a4be23a0edc80 — pure-event, idempotent.

Runnable via:
    python -m openbankapi.seed.run --auth0-sub auth0|6a90f3247c7a4be23a0edc80 [--reset]
    python -m openbankapi.seed.demo --auth0-sub ...   (alias)

and via Docker:
    docker compose up --build          (auto, idempotent)
    docker compose run seed python -m openbankapi.seed.run --auth0-sub ... --reset
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select, text

from openbankapi.config import Settings
from openbankapi.domain.service import AccountService
from openbankapi.domain.service.card_account_service import CardAccountService
from openbankapi.infra.database.config.session import create_engine, create_sessionmaker
from openbankapi.infra.database.repositories import (
    PostgresAccountRepository,
    PostgresCardAccountRepository,
    PostgresCardRepository,
    PostgresCustomerRepository,
)
from openbankapi.infra.database.schemas.models import (
    AccountORM,
    CardAccountORM,
    CardMovementORM,
    CardORM,
    CustomerORM,
    InstallmentORM,
    StatementORM,
    TransactionORM,
)
from openbankapi.infra.kafka.repositories import KafkaEventPublisherRepository
from openbankapi.seed.cycles import run_billing_cycles

Scenario = Literal["demo"]

DEFAULT_SUB = "auth0|6a90f3247c7a4be23a0edc80"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo seed (pure-event, idempotent).")
    parser.add_argument("--auth0-sub", required=True, help="Auth0 sub to seed")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate seed data")
    parser.add_argument("--scenario", default="demo", choices=["demo"], help="Scenario name")
    parser.add_argument("--no-backdate", action="store_true", help="Skip occurred_at backdating")
    parser.add_argument("--skip-kafka", action="store_true", help="Skip Kafka publishes (DB only, for tests)")
    return parser.parse_args(argv)


def _seed_identification_number(sub: str) -> str:
    suffix = sub.split("|")[-1][-8:] if "|" in sub else sub[-8:]
    return f"SEED-{suffix.upper()}"


async def _reset_customer(sessionmaker, sub: str) -> None:
    """Delete seed customer and all FK-descendant rows."""
    async with sessionmaker() as session:
        cust_id = await session.scalar(select(CustomerORM.id).where(CustomerORM.auth0_sub == sub))
        if cust_id is None:
            print(f"[reset] no customer for {sub}, nothing to delete")
            return
        # Collect ids for cascading deletes
        account_ids = list(await session.scalars(select(AccountORM.id).where(AccountORM.customer_id == cust_id)))
        card_account_ids = list(
            await session.scalars(select(CardAccountORM.id).where(CardAccountORM.customer_id == cust_id))
        )
        card_ids: list[UUID] = []
        if card_account_ids:
            card_ids = list(
                await session.scalars(select(CardORM.id).where(CardORM.card_account_id.in_(card_account_ids)))
            )
        # Order: leaf -> root
        if card_ids:
            await session.execute(delete(InstallmentORM).where(InstallmentORM.card_movement_id.in_(
                select(CardMovementORM.id).where(CardMovementORM.card_id.in_(card_ids))
            )))
            await session.execute(delete(StatementORM).where(StatementORM.card_account_id.in_(card_account_ids)))
            await session.execute(delete(CardMovementORM).where(CardMovementORM.card_id.in_(card_ids)))
            await session.execute(delete(CardORM).where(CardORM.id.in_(card_ids)))
        if card_account_ids:
            await session.execute(delete(CardAccountORM).where(CardAccountORM.id.in_(card_account_ids)))
        if account_ids:
            # transactions reference account_number strings, not FK, so delete by number
            acct_numbers = list(await session.scalars(select(AccountORM.account_number).where(AccountORM.id.in_(account_ids))))
            if acct_numbers:
                await session.execute(delete(TransactionORM).where(TransactionORM.account_number.in_(acct_numbers)))
                # deposits via transactions.movement_id cascade, but clean anyway
                await session.execute(text("DELETE FROM deposits WHERE movement_id IN (SELECT id FROM transactions WHERE account_number = ANY(:nums))"), {"nums": acct_numbers})
        if account_ids:
            await session.execute(delete(AccountORM).where(AccountORM.id.in_(account_ids)))
        await session.execute(delete(CustomerORM).where(CustomerORM.id == cust_id))
        await session.commit()
        print(f"[reset] deleted customer {cust_id} and descendants")


async def _ensure_customer(sessionmaker, sub: str):
    async with sessionmaker.begin() as session:
        repo = PostgresCustomerRepository(session)
        existing = await repo.get_by_auth0_sub(sub)
        if existing is not None:
            print(f"[customer] reuse {existing.id} ({sub})")
            return existing
        ident = _seed_identification_number(sub)
        # If ident collides with previous non-sub customer, make unique
        customer = await repo.create(
            identification_number=ident,
            first_name="Demo",
            last_name="User",
            date_of_birth=date(1990, 1, 15),
            gender="M",
            auth0_sub=sub,
        )
        print(f"[customer] created {customer.id} ident={ident}")
        return customer


async def _ensure_accounts(sessionmaker, customer_id: UUID):
    from openbankapi.domain.model import Account

    async with sessionmaker() as session:
        repo = PostgresAccountRepository(session)
        page = await repo.list_by_customer(customer_id, limit=10, offset=0)
        existing: list[Account] = list(page.items)
        if len(existing) >= 3:
            print(f"[accounts] reuse {len(existing)} accounts")
            return sorted(existing, key=lambda a: a.created_at)

        # Create missing accounts up to 3
        needed = 3 - len(existing)
        created: list[Account] = []
        for _ in range(needed):
            acct = await repo.create(currency="USD", customer_id=customer_id)
            created.append(acct)
            print(f"[accounts] created {acct.account_number} ({acct.id})")
        await session.commit()

    # Re-read
    async with sessionmaker() as session:
        repo = PostgresAccountRepository(session)
        page = await repo.list_by_customer(customer_id, limit=10, offset=0)
        accounts = sorted(page.items, key=lambda a: a.created_at)
        for a in accounts:
            print(f"  - {a.account_number} balance={a.balance} {a.currency}")
        return accounts


def _publish_opening_balances(settings: Settings, accounts, skip_kafka: bool) -> None:
    if skip_kafka:
        print("[balances] skip-kafka: not publishing incoming_payment")
        return
    publisher = KafkaEventPublisherRepository(settings)
    service = AccountService(settings, repository=None, publisher=publisher)
    # cents: PRIMARY 500k, SAVINGS 200k, third 100k
    amounts = [500_000, 200_000, 100_000]
    for acct, cents in zip(accounts, amounts):
        service.credit_opening_balance(acct.account_number, cents)
        print(f"[balances] published credit:seed {acct.account_number} {cents} cents")
    publisher.close()
    print("[balances] Flink will project balances within ~5s (checkpoint interval)")


async def _ensure_card_accounts(sessionmaker, customer_id: UUID, paying_account_id: UUID):
    async with sessionmaker() as session:
        repo = PostgresCardAccountRepository(session)
        card_repo = PostgresCardRepository(session)
        page = await repo.list_by_customer(customer_id, limit=10, offset=0)
        if len(page.items) >= 2:
            print(f"[card_accounts] reuse {len(page.items)} card accounts")
            # Need cards too
            cards = []
            for ca in page.items:
                card = await card_repo.get_active_for_account(ca.id)
                cards.append((ca, card))
            for ca, card in cards:
                print(f"  - card_account {ca.id} limit={ca.credit_limit} card={card.card_number if card else '?'}")
            return [(ca, card) for ca, card in cards if card is not None]

        svc = CardAccountService(repo, card_repo)
        ca1, card1 = await svc.issue_card_account(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=Decimal("5000.00")
        )
        print(f"[card_accounts] created CardA {ca1.id} limit=5000 card={card1.card_number}")
        ca2, card2 = await svc.issue_card_account(
            customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=Decimal("10000.00")
        )
        print(f"[card_accounts] created CardB {ca2.id} limit=10000 card={card2.card_number}")
        await session.commit()
        return [(ca1, card1), (ca2, card2)]


def _publish_transfers(settings: Settings, accounts, skip_kafka: bool) -> None:
    if skip_kafka or len(accounts) < 2:
        print("[transfers] skip")
        return
    publisher = KafkaEventPublisherRepository(settings)
    # Two transfers: PRIMARY->SAVINGS $200, SAVINGS->PRIMARY $50
    # Wire shape matches domain.to_wire with minimal fields (same-currency, no conversion)
    primary, savings = accounts[0].account_number, accounts[1].account_number
    for src, dst, amount_cents in [(primary, savings, 20000), (savings, primary, 5000)]:
        req_id = str(uuid.uuid4())
        fee = min(25, amount_cents)
        wire = {
            "type": "transfer_requested",
            "request_id": req_id,
            "source_account": src,
            "destination_account": dst,
            "fees_account": settings.fees_account,
            "amount": amount_cents,
            "fee_amount": fee,
            "ts": _now_iso(),
        }
        publisher.publish(topic=settings.account_events_topic, key=src, value=wire)
        print(f"[transfers] {req_id[:8]} {src} -> {dst} ${amount_cents/100:.2f} fee {fee}c")
    publisher.close()


def _publish_deposit(settings: Settings, accounts, skip_kafka: bool) -> None:
    if skip_kafka or not accounts:
        print("[deposits] skip")
        return
    publisher = KafkaEventPublisherRepository(settings)
    acct = accounts[0].account_number
    req_id = str(uuid.uuid4())
    amount = 30000  # cents $300
    wire = {
        "type": "deposit",
        "request_id": req_id,
        "account_id": acct,
        "amount": amount,
        "currency": "USD",
        "amount_applied": amount,
        "admin_id": "seed",
        "leg": "deposit",
        "ts": _now_iso(),
        "reason": "Demo seed deposit",
    }
    publisher.publish(topic=settings.account_events_topic, key=acct, value=wire)
    print(f"[deposits] {req_id[:8]} -> {acct} ${amount/100:.2f}")
    publisher.close()


async def _seed_demo(auth0_sub: str, reset: bool, no_backdate: bool, skip_kafka: bool) -> int:
    settings = Settings.from_env()
    engine = create_engine(settings.database_dsn)
    sessionmaker = create_sessionmaker(engine)
    try:
        if reset:
            await _reset_customer(sessionmaker, auth0_sub)

        # Idempotency guard: if not reset and already seeded, skip publishes
        already_seeded = False
        async with sessionmaker() as session:
            cust = await PostgresCustomerRepository(session).get_by_auth0_sub(auth0_sub)
            if cust is not None and not reset:
                page = await PostgresCardAccountRepository(session).list_by_customer(cust.id, limit=10, offset=0)
                if len(page.items) >= 2:
                    already_seeded = True

        customer = await _ensure_customer(sessionmaker, auth0_sub)
        accounts = await _ensure_accounts(sessionmaker, customer.id)

        if already_seeded:
            print("[seed] already seeded (2 card_accounts exist) — skipping publishes (use --reset to force).")
            print("[verify] GET /accounts?customer_id=..., GET /cards, GET /transactions")
            return 0

        _publish_opening_balances(settings, accounts, skip_kafka)
        # Small pause before card creation is not needed; accounts are committed

        card_pairs = await _ensure_card_accounts(sessionmaker, customer.id, accounts[0].id)

        if not skip_kafka and card_pairs:
            print("[cycles] waiting 5s for card accounts to settle before publishing cycle purchases...")
            await asyncio.sleep(5)
        for card_account, card in card_pairs:
            await run_billing_cycles(settings, sessionmaker, card_account, card, accounts[0], skip_kafka, no_backdate)

        _publish_transfers(settings, accounts, skip_kafka)
        _publish_deposit(settings, accounts, skip_kafka)

        print("[seed] complete.")
        print("[verify] curl /accounts, /cards, /transactions (after ~5s Flink checkpoint)")
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return asyncio.run(_seed_demo(args.auth0_sub, args.reset, args.no_backdate, args.skip_kafka))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
