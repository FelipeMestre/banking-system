"""RED for FX-11: `applied_rates` migration — real Postgres, real Alembic.

Uses the dedicated `fx_test_dsn` fixture (see `db_fixtures.py`) rather than
the shared dev Postgres `docker-compose.yml` starts, because that database
can already sit on an unrelated migration history.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from openbankapi.infra.database.config.session import create_engine
from openbankapi.tests.db_fixtures import downgrade_one, downgrade_to, migrate_to_head

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "infra" / "database" / "config" / "alembic.ini"


async def _table_info(dsn: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            columns = await conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'applied_rates' ORDER BY ordinal_position"
            )
            column_rows = columns.fetchall()
            count_result = await conn.exec_driver_sql("SELECT count(*) FROM applied_rates")
            row_count = count_result.scalar_one()
            constraints = await conn.exec_driver_sql(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'applied_rates' AND constraint_type = 'CHECK'"
            )
            constraint_names = [row[0] for row in constraints.fetchall()]
            return column_rows, row_count, constraint_names
    finally:
        await engine.dispose()


async def _table_exists(dsn: str) -> bool:
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql("SELECT to_regclass('public.applied_rates')")
            return result.scalar_one() is not None
    finally:
        await engine.dispose()


def test_migration_creates_applied_rates_table_empty(fx_test_dsn):
    columns, row_count, constraint_names = asyncio.run(_table_info(fx_test_dsn))
    names = {row[0] for row in columns}
    assert names == {
        "id",
        "pair",
        "mid_rate",
        "applied_rate",
        "margin",
        "direction",
        "source_ts",
        "created_at",
    }
    by_name = {row[0]: row for row in columns}
    assert by_name["pair"][1] == "character varying"
    for not_null_column in (
        "id",
        "pair",
        "mid_rate",
        "applied_rate",
        "margin",
        "direction",
        "source_ts",
        "created_at",
    ):
        assert by_name[not_null_column][2] == "NO", f"{not_null_column} must be NOT NULL"
    assert row_count == 0
    assert len(constraint_names) >= 1, "the direction CHECK constraint must exist"


def test_downgrade_drops_applied_rates_table(fx_test_dsn):
    assert asyncio.run(_table_exists(fx_test_dsn)) is True
    # Post-FX-16, `applied_rates` sits two revisions before `head` (the merge
    # then the `applied_rate_id` column both come after it) — target the
    # pre-applied_rates revision directly rather than stepping `-1` twice.
    downgrade_to("a1c9f3d6e21b", fx_test_dsn)
    try:
        assert asyncio.run(_table_exists(fx_test_dsn)) is False
    finally:
        # Restore head so later tests (repository/router, which depend on
        # this same session-scoped fixture) still see the table.
        migrate_to_head(fx_test_dsn)


# --- RED for FX-16: single-head merge + applied_rate_id linkage column ------


async def _heads(dsn: str) -> set[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(_ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    return set(script.get_heads())


async def _transactions_applied_rate_id_info(dsn: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            columns = await conn.exec_driver_sql(
                "SELECT column_name, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'transactions' AND column_name = 'applied_rate_id'"
            )
            column_rows = columns.fetchall()
            fk_result = await conn.exec_driver_sql(
                "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "ON tc.constraint_name = kcu.constraint_name "
                "WHERE tc.table_name = 'transactions' AND tc.constraint_type = 'FOREIGN KEY' "
                "AND kcu.column_name = 'applied_rate_id'"
            )
            fk_rows = fk_result.fetchall()
            return column_rows, fk_rows
    finally:
        await engine.dispose()


async def _transactions_applied_rate_id_exists(dsn: str) -> bool:
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'transactions' AND column_name = 'applied_rate_id'"
            )
            return result.fetchone() is not None
    finally:
        await engine.dispose()


def test_merge_migration_produces_a_single_head(fx_test_dsn):
    heads = asyncio.run(_heads(fx_test_dsn))
    assert len(heads) == 1, f"expected exactly one head, found {heads}"


def test_transactions_applied_rate_id_is_nullable_and_fk(fx_test_dsn):
    column_rows, fk_rows = asyncio.run(_transactions_applied_rate_id_info(fx_test_dsn))
    assert len(column_rows) == 1
    assert column_rows[0][1] == "YES", "applied_rate_id must be nullable"
    assert len(fk_rows) >= 1, "applied_rate_id must be FK-constrained to applied_rates(id)"


def test_downgrade_of_applied_rate_id_column_restores_prior_state(fx_test_dsn):
    assert asyncio.run(_transactions_applied_rate_id_exists(fx_test_dsn)) is True
    downgrade_one(fx_test_dsn)
    try:
        assert asyncio.run(_transactions_applied_rate_id_exists(fx_test_dsn)) is False
    finally:
        migrate_to_head(fx_test_dsn)
