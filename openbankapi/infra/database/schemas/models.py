"""SQLAlchemy mappings for the schema `infra/database/migrations` creates (spec §3).

Alembic owns the DDL (spec §10): nothing ever calls `Base.metadata.create_all`.
These classes describe the tables the baseline migration creates — they must
stay in lockstep with it, the same way they used to have to match `init.sql`.
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


def _created() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LocationORM(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class BranchORM(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = _pk()
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class CustomerORM(Base):
    """No `age` column, by design (spec §3.4) — it is derived on read.

    `date_of_birth` and `gender` are personal data; nothing may log them.
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = _pk()
    identification_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[dt.date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Set only via PATCH /customers/{id}/auth0-link (spec §1.1); never backfilled.
    auth0_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class AccountORM(Base):
    """`balance` is a projection, not state this table owns (spec §3.5).

    The only writer is the `account-balances` consumer, reached through
    `IAccountBalanceProjection`. No CRUD path can set it.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(r"account_number ~ '^[0-9]{16}$'", name="accounts_account_number_check"),
    )

    id: Mapped[uuid.UUID] = _pk()
    # CHAR(16), not VARCHAR: leading zeros are significant because this value is
    # the Kafka partition key. '0000000000000001' and '1' are different shards.
    account_number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class AppliedRateORM(Base):
    """Passive audit row for a margin-adjusted quote (FX-14).

    Built and migrated in this phase, but nothing writes to it yet — no
    route calls `IAppliedRateRepository.insert()` (FX-13/FX-15 scope guard).
    """

    __tablename__ = "applied_rates"
    __table_args__ = (
        CheckConstraint("direction IN ('credit', 'debit')", name="applied_rates_direction_check"),
    )

    id: Mapped[uuid.UUID] = _pk()
    pair: Mapped[str] = mapped_column(String(7), nullable=False)
    mid_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    applied_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    margin: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    source_ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
class TransactionORM(Base):
    """The transactions read model (spec §3). Written only by `TransactionConsumer`.

    `UNIQUE(request_id, account_number, type)` is what makes at-least-once
    Kafka redelivery idempotent: a redelivered event maps to the exact same
    three values, so `INSERT ... ON CONFLICT DO NOTHING` is a true no-op.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('debit', 'credit', 'declined')", name="transactions_type_check"),
        UniqueConstraint(
            "request_id", "account_number", "type", name="transactions_request_id_account_number_type_key"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    request_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    account_number: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counterparty_account: Mapped[str] = mapped_column(String(16), nullable=False)
    decline_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt.datetime] = _created()
    # Nullable, additive (FX-16): only a settled leg that carried a currency
    # conversion links to its audit row; same-currency legs and outgoing/
    # declined rows always leave this NULL.
    applied_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("applied_rates.id"), nullable=True
    )


class CardAccountORM(Base):
    """The credit-card line: a customer's parent aggregate for `cards` (Phase 1)."""

    __tablename__ = "card_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','blocked','closed')", name="card_accounts_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    paying_account_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class CardORM(Base):
    """A physical/virtual card belonging to a `CardAccountORM` (Phase 1)."""

    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint(r"card_number ~ '^[0-9]{16}$'", name="cards_card_number_check"),
        CheckConstraint(
            "status IN ('active','blocked','replaced','expired')", name="cards_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    card_account_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("card_accounts.id"), nullable=False
    )
    card_number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    expiration_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class StatementORM(Base):
    """A card account's billing period (Phase 1: structural only, no writers)."""

    __tablename__ = "statements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','closed','paid','overdue')", name="statements_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    card_account_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("card_accounts.id"), nullable=False
    )
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    minimum_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class CardMovementORM(Base):
    """A card ledger entry (Phase 1: structural only, no writers).

    No `updated_at`: immutable audit rows, mirrors `AppliedRateORM`.
    """

    __tablename__ = "card_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IS NULL OR movement_type IN "
            "('purchase','payment','fee','interest','refund','declined')",
            name="card_movements_movement_type_check",
        ),
        UniqueConstraint(
            "request_id", "movement_type", name="card_movements_request_id_movement_type_key"
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cards.id"), nullable=False
    )
    applied_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("applied_rates.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    movement_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = _created()


class InstallmentORM(Base):
    """One installment of a card movement (Phase 1: structural only, no writers).

    No `updated_at`: immutable audit rows, same rationale as `CardMovementORM`.
    """

    __tablename__ = "installments"
    __table_args__ = (
        CheckConstraint(
            "status IS NULL OR status IN ('pending','paid','overdue')",
            name="installments_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    card_movement_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("card_movements.id"), nullable=False
    )
    installment_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[dt.datetime] = _created()
