"""Shared real-Postgres test infrastructure — FX-14's dedicated test database.

This repo's existing tests never open a real database connection: every
repository/router test (`conftest.py`'s `build()` harness) injects an
in-memory `Fake*Repository` via `app.dependency_overrides` instead. FX-14
needs a genuine Postgres round-trip — "mocking the database in integration
tests" is a documented anti-pattern in this repo's own AGENTS.MD — so this
module is new test-only infrastructure, built directly on
`infra.database.config.session`'s own `create_engine`/`create_sessionmaker`,
the same two functions `main.py` uses to build the real app's engine.

A SEPARATE database (`openbank_fx_test` by default, overridable via
`FX_TEST_DATABASE_DSN`) is used rather than this repo's shared `openbank` dev
database: the dev Postgres volume `docker-compose.yml` starts can already sit
on an unrelated migration history (a different branch/worktree may have
migrated it — confirmed during this change: the running dev database was at
revision `b3e7a9c1f4d0`, which does not even exist in this worktree's
migration chain). Running `alembic upgrade head` against that shared database
would be unsafe. A dedicated database, migrated from scratch against *this*
worktree's own migration chain, sidesteps the problem entirely.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession

from openbankapi.infra.database.config.session import create_engine, create_sessionmaker

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "infra" / "database" / "config" / "alembic.ini"

TEST_DATABASE_DSN = os.getenv(
    "FX_TEST_DATABASE_DSN",
    "postgresql+asyncpg://openbank:openbank@localhost:5432/openbank_fx_test",
)


def _admin_dsn(dsn: str) -> str:
    """Same server, `postgres` maintenance database, plain (non-async) driver."""
    parts = urlsplit(dsn.replace("+asyncpg", ""))
    return urlunsplit(parts._replace(path="/postgres"))


def _database_name(dsn: str) -> str:
    return urlsplit(dsn).path.lstrip("/")


async def _ensure_database_exists(dsn: str) -> None:
    db_name = _database_name(dsn)
    conn = await asyncpg.connect(_admin_dsn(dsn))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


def _run_alembic(command_name: str, revision: str, dsn: str) -> None:
    # env.py (infra/database/migrations/env.py) resolves its URL from
    # `Settings.from_env().database_dsn`, i.e. the DATABASE_DSN env var — not
    # from the Config object's static `sqlalchemy.url` — so that env var is
    # the actual way to point a migration run at the test database.
    from alembic import command
    from alembic.config import Config

    config = Config(str(_ALEMBIC_INI))
    previous_dsn = os.environ.get("DATABASE_DSN")
    os.environ["DATABASE_DSN"] = dsn
    try:
        getattr(command, command_name)(config, revision)
    finally:
        if previous_dsn is None:
            os.environ.pop("DATABASE_DSN", None)
        else:
            os.environ["DATABASE_DSN"] = previous_dsn


def migrate_to_head(dsn: str = TEST_DATABASE_DSN) -> None:
    """Create the test database if needed and upgrade it to `head`.

    Idempotent: Alembic no-ops when the database is already at `head`, so
    this is safe to call once per test session or repeatedly across files.
    """
    asyncio.run(_ensure_database_exists(dsn))
    _run_alembic("upgrade", "head", dsn)


def downgrade_one(dsn: str = TEST_DATABASE_DSN) -> None:
    _run_alembic("downgrade", "-1", dsn)


@asynccontextmanager
async def rollback_session(dsn: str = TEST_DATABASE_DSN) -> AsyncIterator[AsyncSession]:
    """One real Postgres session per test, wrapped in a transaction that is
    always rolled back — no test leaves a row behind for the next one.

    Built from `session.create_engine`/`session.create_sessionmaker`, the
    same two functions `main.py` uses for the real app's engine. The engine
    is created and disposed inside the SAME event loop the caller drives:
    this repo has no `pytest-asyncio`, so callers wrap this in
    `asyncio.run(...)` exactly like every other async test here already does
    (see `test_foreign_exchange_cache_service.py`) — an `AsyncEngine`/pool
    created in one `asyncio.run()` cannot be reused from another.
    """
    engine = create_engine(dsn)
    sessionmaker = create_sessionmaker(engine)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            session = sessionmaker(bind=conn)
            try:
                yield session
            finally:
                await session.close()
                await transaction.rollback()
    finally:
        await engine.dispose()
