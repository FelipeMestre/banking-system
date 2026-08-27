"""Async engine, session factory, and the per-request Unit of Work.

The engine is built by `main.py` and injected, never created at import time: a
module-level engine binds to whatever event loop happens to import it first,
which breaks tests and any second loop.
"""
from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.requests import HTTPConnection


def create_engine(dsn: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        dsn,
        echo=echo,
        pool_pre_ping=True,  # a recycled Postgres connection fails on first use otherwise
        pool_size=10,
        max_overflow=5,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: rows are mapped to frozen domain entities before
    # the session closes, and re-fetching an expired attribute afterwards would
    # raise outside the async context.
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(conn: HTTPConnection) -> AsyncIterator[AsyncSession]:
    """One session, one transaction, per request — the Unit of Work boundary.

    Every repository built on this session only ever flushes; it never commits
    or opens its own transaction. This function is the single place a request's
    writes become durable. If anything raises after the session was handed out
    — a repository's own constraint violation, or a later step in the same
    request failing for an unrelated reason — everything this request touched
    rolls back together, not just whichever operation happened to fail.

    Typed as `HTTPConnection` (the base `Request` and `WebSocket` both share),
    not `Request`, so the exact same dependency function also works from the
    transfer endpoints' WebSocket route, matching how `get_settings`/`get_cache`
    already read `conn.app.state` in `controllers/dependencies.py`.
    """
    sessionmaker: async_sessionmaker[AsyncSession] = conn.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
