"""SQLAlchemy mappings for the schema in `infra/postgres/init.sql` (spec §3).

These classes DESCRIBE tables they do not own. `init.sql` is the only thing that
creates them (spec §10): there is no Alembic here and nothing ever calls
`Base.metadata.create_all`. Two sources of DDL is how a schema and its mapping
drift apart without anyone noticing.
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


class LocacionORM(Base):
    __tablename__ = "locaciones"

    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class SucursalORM(Base):
    __tablename__ = "sucursales"

    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    locacion_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("locaciones.id"), nullable=False
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class ClienteORM(Base):
    """No `age` column, by design (spec §3.4) — it is derived on read.

    `fecha_nacimiento` and `genero` are personal data; nothing may log them.
    """

    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = _pk()
    numero_identificacion: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_nacimiento: Mapped[dt.date] = mapped_column(Date, nullable=False)
    genero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()


class CuentaORM(Base):
    """`saldo` is a projection, not state this table owns (spec §3.5).

    The only writer is the `account-balances` consumer, reached through
    `ICuentaBalanceProjection`. No CRUD path can set it.
    """

    __tablename__ = "cuentas"
    __table_args__ = (
        CheckConstraint(r"numero_cuenta ~ '^[0-9]{16}$'", name="cuentas_numero_cuenta_check"),
    )

    id: Mapped[uuid.UUID] = _pk()
    # CHAR(16), not VARCHAR: leading zeros are significant because this value is
    # the Kafka partition key. '0000000000000001' and '1' are different shards.
    numero_cuenta: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False
    )
    sucursal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sucursales.id"), nullable=False
    )
    saldo: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activa")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _created()
