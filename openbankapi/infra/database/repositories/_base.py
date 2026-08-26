"""Shared session handling for the Postgres repositories.

Every method opens exactly one session. Reads use a plain session; writes use
`sessionmaker.begin()` so the commit happens on a clean exit.

The `try/except IntegrityError` must wrap the WHOLE `async with` block, not just
the `execute`: a constraint can surface either at flush time or at the COMMIT
that `begin()` issues on exit, and only one of those is inside the execute call.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional, Sequence, Tuple, Type, TypeVar

from sqlalchemy import func, select, update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..errors import translate
from ..interfaces.common import Page

R = TypeVar("R")


class PostgresRepository:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def _fetch_one(self, model: Type[Any], *where: Any) -> Optional[Any]:
        async with self._sessionmaker() as session:
            result = await session.execute(select(model).where(*where))
            return result.scalar_one_or_none()

    async def _fetch_page(
        self, model: Type[Any], *, limit: int, offset: int
    ) -> Tuple[Sequence[Any], int]:
        async with self._sessionmaker() as session:
            total = await session.scalar(select(func.count()).select_from(model))
            # The tie-break on id is what makes an offset page stable when two
            # rows share a created_at.
            rows = await session.execute(
                select(model)
                .order_by(model.created_at.desc(), model.id.desc())
                .limit(limit)
                .offset(offset)
            )
            return rows.scalars().all(), int(total or 0)

    async def _insert(self, model: Type[Any], values: Dict[str, Any]) -> Any:
        try:
            async with self._sessionmaker.begin() as session:
                row = model(**values)
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return row
        except IntegrityError as error:
            raise translate(error, values=values) from error

    async def _update(
        self, model: Type[Any], where: Any, values: Dict[str, Any]
    ) -> Optional[Any]:
        """Apply only the fields the caller actually supplied.

        An empty `values` still returns the current row: a PUT that changes
        nothing is a no-op, not a 404.
        """
        changes = {k: v for k, v in values.items() if v is not None}
        try:
            async with self._sessionmaker.begin() as session:
                if changes:
                    changes["updated_at"] = dt.datetime.now(dt.timezone.utc)
                    await session.execute(sql_update(model).where(where).values(**changes))
                result = await session.execute(select(model).where(where))
                return result.scalar_one_or_none()
        except IntegrityError as error:
            raise translate(error, values=changes) from error


def page_of(items, total: int, limit: int, offset: int) -> Page:
    return Page(items=list(items), total=total, limit=limit, offset=offset)
