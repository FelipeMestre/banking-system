"""SQLAlchemy mappings for the schema `infra/database/migrations` creates (spec §3).

Alembic owns the DDL (spec §10): nothing ever calls `Base.metadata.create_all`.
These classes describe the tables the baseline migration creates — they must
stay in lockstep with it, the same way they used to have to match `init.sql`.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
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
