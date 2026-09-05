"""RED for Credit Cards Phase 1: ORM mapping for the 5 new tables (T3).

Inspects `Base.metadata` directly — no DB connection needed, matching how
`AccountORM`/`AppliedRateORM` are structurally verifiable without Postgres.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.dialects.postgresql import UUID as PgUUID

from openbankapi.infra.database.schemas.models import (
    Base,
    CardAccountORM,
    CardMovementORM,
    CardORM,
    InstallmentORM,
    StatementORM,
)


def test_card_account_orm_table_name_and_pk():
    assert CardAccountORM.__tablename__ == "card_accounts"
    assert CardAccountORM.__table__.c.id.primary_key


def test_card_orm_table_name_and_unique_card_number():
    assert CardORM.__tablename__ == "cards"
    assert CardORM.__table__.c.card_number.unique is True


def test_statement_orm_table_name():
    assert StatementORM.__tablename__ == "statements"


def test_card_movement_orm_table_name_and_nullable_applied_rate_id():
    assert CardMovementORM.__tablename__ == "card_movements"
    assert CardMovementORM.__table__.c.applied_rate_id.nullable is True


def test_installment_orm_table_name():
    assert InstallmentORM.__tablename__ == "installments"


def test_all_five_tables_are_registered_on_base_metadata():
    table_names = set(Base.metadata.tables.keys())
    assert {"card_accounts", "cards", "statements", "card_movements", "installments"} <= table_names


def test_card_account_column_types_match_ddl():
    columns = CardAccountORM.__table__.c
    assert isinstance(columns.id.type, PgUUID)
    assert str(columns.credit_limit.type) == "NUMERIC(14, 2)"
    assert columns.status.type.length == 20


def test_card_number_column_length():
    assert CardORM.__table__.c.card_number.type.length == 16
