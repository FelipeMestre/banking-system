"""Billing-cycle orchestration for the demo seed — publishes 3 sequential
statement cycles per card so `StatementService`'s cross-cycle math (interest
carried on an unpaid balance) actually gets exercised, not just a single
isolated `close_statement` call."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from openbankapi.config import Settings
from openbankapi.domain.model import Statement
from openbankapi.domain.service.statement_service import StatementService
from openbankapi.infra.database.repositories import (
    PostgresCardMovementRepository,
    PostgresCardRepository,
    PostgresInstallmentRepository,
    PostgresStatementRepository,
)
from openbankapi.infra.kafka.repositories import KafkaEventPublisherRepository
from openbankapi.seed.backdate import backdate_to_window
from openbankapi.seed.catalog import purchases_for_cycle

# A "cycle" is one billing statement period (domain/service/statement_service.py).
# 3 cycles of 30 days, ending 85/55/25 days ago, so cycles 1-2 already have a
# past due_date (statement_service only finalizes payment outcome for an
# exact due_date match) while the (unclosed) 4th cycle after cycle 3's
# period_end is the genuinely live, still-open current cycle.
#
# Cycle 3 (the last CLOSED one) is deliberately left unpaid AND with a
# due_date already in the past (period_end 25 days ago + the default 20-day
# due-date offset = 5 days overdue) — this exercises
# `current_cycle_current-cycle`'s single most safety-critical branch: while
# this statement's own `run_due_date_check` has not yet finalized it (still
# `status=closed`), the live projection MUST derive its outstanding balance
# via a live `sum_payments` call, never the statement's frozen `paid_amount`
# field. The seed script intentionally never calls `run_due_date_check` for
# this cycle (see the `pay_ratio <= 0: continue` guard below) so this state
# survives until the batch worker's own next scheduled tick finalizes it —
# reseed and verify promptly after running this script.
CYCLE_COUNT = 3
CYCLE_LENGTH_DAYS = 30
FIRST_CYCLE_LAG_DAYS = 85
# cycle 1: 40% paid -> carries unpaid balance + interest into cycle 2.
# cycle 2: paid in full -> clean before cycle 3.
# cycle 3: unpaid, due_date already past, NOT finalized -> exercises the
#   overdue-previous-cycle live-computation branch for the current cycle.
CYCLE_PAY_RATIOS: tuple[Decimal, ...] = (Decimal("0.4"), Decimal("1.0"), Decimal("0"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cycle_bounds(cycle_index: int, today: date) -> tuple[date, date]:
    """Mirrors `StatementService.close_statement`'s own period_start
    derivation so the movements we backdate land inside the exact window
    that statement will sum — this only holds because we always close cycle
    0 first, sequentially, as the very first statement for the account."""
    period_end = today - timedelta(days=FIRST_CYCLE_LAG_DAYS - cycle_index * CYCLE_LENGTH_DAYS)
    if cycle_index == 0:
        period_start = period_end - timedelta(days=CYCLE_LENGTH_DAYS)
    else:
        previous_period_end = period_end - timedelta(days=CYCLE_LENGTH_DAYS)
        period_start = previous_period_end + timedelta(days=1)
    return period_start, period_end


def _publish_cycle_purchases(
    settings: Settings, card_account, card, cycle_index: int, skip_kafka: bool, card_index: int = 0
) -> list[str]:
    if skip_kafka:
        print(f"[cycle {cycle_index + 1}] skip-kafka: not publishing purchases")
        return []
    publisher = KafkaEventPublisherRepository(settings)
    request_ids: list[str] = []
    for spec in purchases_for_cycle(cycle_index, card_index):
        rid = str(uuid.uuid4())
        request_ids.append(rid)
        wire = {
            "type": "purchase_requested",
            "request_id": rid,
            "card_id": str(card.id),
            "card_account_id": str(card_account.id),
            "amount": str(Decimal(spec.amount_usd).quantize(Decimal("0.01"))),
            "currency": "USD",
            "amount_usd": float(spec.amount_usd),
            "credit_limit": float(card_account.credit_limit),
            "installments": spec.installments,
            "description": spec.description,
            "ts": _now_iso(),
        }
        publisher.publish(topic=settings.card_events_topic, key=str(card_account.id), value=wire)
    publisher.close()
    print(f"[cycle {cycle_index + 1}] published {len(request_ids)} purchase_requested for card {card.card_number}")
    return request_ids


def _publish_payment(
    settings: Settings, card_account, card, paying_account, amount_cents: int, skip_kafka: bool
) -> Optional[str]:
    if skip_kafka or amount_cents <= 0:
        return None
    publisher = KafkaEventPublisherRepository(settings)
    rid = str(uuid.uuid4())
    wire = {
        "type": "payment_requested",
        "request_id": rid,
        "destination_account": card.card_number,
        "card_account_id": str(card_account.id),
        "card_id": str(card.id),
        "amount": amount_cents,
        "amount_usd": amount_cents / 100,
        "ts": _now_iso(),
    }
    publisher.publish(topic=settings.account_events_topic, key=paying_account.account_number, value=wire)
    publisher.close()
    print(f"[payment] {rid[:8]} card {card.card_number} ${amount_cents / 100:.2f}")
    return rid


def _build_statement_service(session, settings: Settings) -> StatementService:
    return StatementService(
        PostgresStatementRepository(session),
        PostgresCardMovementRepository(session),
        PostgresInstallmentRepository(session),
        PostgresCardRepository(session),
        credit_card_apr=settings.credit_card_apr,
        late_fee_amount=settings.late_fee_amount,
        minimum_payment_rate=settings.minimum_payment_rate,
        due_date_offset_days=settings.due_date_offset_days,
    )


async def run_billing_cycles(
    settings: Settings,
    sessionmaker,
    card_account,
    card,
    paying_account,
    skip_kafka: bool,
    no_backdate: bool,
    card_index: int = 0,
) -> None:
    """Closes `CYCLE_COUNT` sequential billing cycles for one card, paying
    each down per `CYCLE_PAY_RATIOS` so cycle 2 provably carries cycle 1's
    unpaid balance forward as interest (statement_service's `total_due`
    computation is otherwise never exercised past a single, isolated cycle).

    `card_index` (0 for the first demo card, 1 for the second, etc.) is
    forwarded to the purchase catalog so multiple demo cards don't all get
    the exact same purchase history — see `catalog.purchases_for_cycle`."""
    today = date.today()
    for cycle_index in range(CYCLE_COUNT):
        period_start, period_end = _cycle_bounds(cycle_index, today)
        request_ids = _publish_cycle_purchases(
            settings, card_account, card, cycle_index, skip_kafka, card_index
        )
        if not skip_kafka and request_ids and not no_backdate:
            await backdate_to_window(sessionmaker, request_ids, period_start, period_end)

        async with sessionmaker.begin() as session:
            statement: Optional[Statement] = await _build_statement_service(session, settings).close_statement(
                card_account.id, period_end
            )
        if statement is None:
            continue
        print(
            f"[cycle {cycle_index + 1}] closed statement {statement.id} "
            f"total_due=${statement.total_due} due={statement.due_date.isoformat()}"
        )

        pay_ratio = CYCLE_PAY_RATIOS[cycle_index]
        if skip_kafka or pay_ratio <= 0 or statement.total_due <= 0:
            continue
        payment_cents = int((statement.total_due * pay_ratio).quantize(Decimal("0.01")) * 100)
        payment_rid = _publish_payment(settings, card_account, card, paying_account, payment_cents, skip_kafka)
        if payment_rid is None:
            continue
        await backdate_to_window(sessionmaker, [payment_rid], period_end, period_end)
        async with sessionmaker.begin() as session:
            await _build_statement_service(session, settings).run_due_date_check(statement.due_date)
        print(f"[cycle {cycle_index + 1}] payment applied, due-date check run for {statement.due_date.isoformat()}")
