"""Async engine and session factory.

The engine is built by `main.py` and injected, never created at import time: a
module-level engine binds to whatever event loop happens to import it first,
which breaks tests and any second loop.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_engine(dsn: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        dsn,
        echo=echo,
        pool_pre_ping=True,  # a recycled Postgres connection fails on first use otherwise
        pool_size=10,
        max_overflow=5,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    # expire_on_commit=False: rows are mapped to frozen domain entities before
    # the session closes, and re-fetching an expired attribute afterwards would
    # raise outside the async context.
    return async_sessionmaker(engine, expire_on_commit=False)
