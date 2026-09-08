"""RED for card-account-admin-audit: migration creates shape (Task 1.2)."""
from __future__ import annotations

import asyncio

from openbankapi.infra.database.config.session import create_engine
from openbankapi.tests.db_fixtures import downgrade_to, migrate_to_head


async def _table_exists(dsn: str, table: str) -> bool:
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(f"SELECT to_regclass('public.{table}')")
            return result.scalar_one() is not None
    finally:
        await engine.dispose()


async def _columns(dsn: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            cols = await conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name='card_account_admin_actions' ORDER BY ordinal_position"
            )
            return cols.fetchall()
    finally:
        await engine.dispose()


async def _indexes(dsn: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='card_account_admin_actions'"
            )
            return result.fetchall()
    finally:
        await engine.dispose()


async def _checks(dsn: str):
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='card_account_admin_actions'::regclass AND contype='c'"
            )
            return result.fetchall()
    finally:
        await engine.dispose()


def test_migration_creates_card_account_admin_actions_shape(fx_test_dsn):
    assert asyncio.run(_table_exists(fx_test_dsn, "card_account_admin_actions")) is True
    cols = asyncio.run(_columns(fx_test_dsn))
    names = {row[0] for row in cols}
    assert names == {"id", "card_account_id", "admin_id", "action", "reason", "details", "created_at"}
    by_name = {row[0]: row for row in cols}
    # NOT NULL checks
    for col in ("id", "card_account_id", "admin_id", "action", "created_at"):
        assert by_name[col][2] == "NO", f"{col} must be NOT NULL"
    for col in ("reason", "details"):
        assert by_name[col][2] == "YES", f"{col} must be nullable"
    checks = asyncio.run(_checks(fx_test_dsn))
    assert any("action" in str(c[1]) and "issue" in str(c[1]) for c in checks), f"CHECK5 missing {checks}"
    indexes = asyncio.run(_indexes(fx_test_dsn))
    # Expect two indexes: (card_account_id, created_at DESC, id DESC) and (admin_id)
    assert len(indexes) >= 2, f"expected >=2 indexes, got {indexes}"
    idx_defs = " ".join(str(i[1]) for i in indexes)
    assert "card_account_id" in idx_defs
    assert "admin_id" in idx_defs


def test_downgrade_drops_card_account_admin_actions(fx_test_dsn):
    assert asyncio.run(_table_exists(fx_test_dsn, "card_account_admin_actions")) is True
    downgrade_to("8f7e6d5c4b3a", fx_test_dsn)
    try:
        assert asyncio.run(_table_exists(fx_test_dsn, "card_account_admin_actions")) is False
    finally:
        migrate_to_head(fx_test_dsn)
