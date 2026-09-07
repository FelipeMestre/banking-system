"""RED for Credit Cards Phase 1: the 5-table migration (T1) — real Postgres.

Reuses the shared `fx_test_dsn` fixture (see `conftest.py`/`db_fixtures.py`):
one dedicated test database, migrated to `head` for the whole session, same
convention as `test_applied_rates_migration.py`.

Environment note: this repository's real-Postgres tests require a reachable
`localhost:5432` (see `db_fixtures.py`). In an environment with no Postgres
available, this file errors at connection time exactly like the 15
pre-existing real-DB tests already in this suite (`test_applied_rate_repository.py`,
`test_applied_rates_migration.py`, `test_transfer_conversion_e2e.py`, etc.) —
that is a documented, pre-existing environment gap, not a regression.
"""
from __future__ import annotations

import asyncio

from openbankapi.infra.database.config.session import create_engine
from openbankapi.tests.db_fixtures import downgrade_to, migrate_to_head

_NEW_TABLES = ("card_accounts", "cards", "statements", "card_movements", "installments")


async def _table_exists(dsn: str, table_name: str) -> bool:
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(f"SELECT to_regclass('public.{table_name}')")
            return result.scalar_one() is not None
    finally:
        await engine.dispose()


async def _constraint_names(dsn: str, table_name: str) -> set[str]:
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(
                "SELECT constraint_name FROM information_schema.table_constraints "
                f"WHERE table_name = '{table_name}'"
            )
            return {row[0] for row in result.fetchall()}
    finally:
        await engine.dispose()


def test_all_five_tables_exist_after_upgrade_head(fx_test_dsn):
    for table in _NEW_TABLES:
        assert asyncio.run(_table_exists(fx_test_dsn, table)) is True, f"{table} missing"


def test_cards_card_number_has_a_unique_constraint(fx_test_dsn):
    names = asyncio.run(_constraint_names(fx_test_dsn, "cards"))
    assert "cards_card_number_key" in names


def test_downgrade_drops_all_five_tables_in_fk_order(fx_test_dsn):
    for table in _NEW_TABLES:
        assert asyncio.run(_table_exists(fx_test_dsn, table)) is True
    downgrade_to("d4f6b2a90c58", fx_test_dsn)
    try:
        for table in _NEW_TABLES:
            assert asyncio.run(_table_exists(fx_test_dsn, table)) is False, f"{table} not dropped"
    finally:
        migrate_to_head(fx_test_dsn)


# --- credit-card-used-balance: used_credit column (Red before migration) ---


async def _column_info(dsn: str, table: str, column: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND column_name = '{column}'"
            )
            row = result.fetchone()
            return row
    finally:
        await engine.dispose()


def test_card_accounts_has_used_credit_column(fx_test_dsn):
    row = asyncio.run(_column_info(fx_test_dsn, "card_accounts", "used_credit"))
    assert row is not None, "used_credit column missing"
    _, data_type, is_nullable, column_default = row
    assert data_type == "bigint", f"expected bigint got {data_type}"
    assert is_nullable == "NO", "used_credit must be NOT NULL"
    assert column_default is not None and "0" in column_default, f"DEFAULT 0 expected got {column_default}"


def test_used_credit_downgrade_drops_column(fx_test_dsn):
    # head has column; downgrade one step should drop it if migration present
    row_before = asyncio.run(_column_info(fx_test_dsn, "card_accounts", "used_credit"))
    assert row_before is not None, "precondition: column must exist at head"
    downgrade_to("9a8b7c6d5e4f", fx_test_dsn)
    try:
        row = asyncio.run(_column_info(fx_test_dsn, "card_accounts", "used_credit"))
        assert row is None, "used_credit should be dropped after downgrade"
    finally:
        migrate_to_head(fx_test_dsn)
        row_after = asyncio.run(_column_info(fx_test_dsn, "card_accounts", "used_credit"))
        assert row_after is not None, "column must be back after re-upgrade"
