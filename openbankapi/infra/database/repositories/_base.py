"""Shared session handling for the Postgres repositories.

Every repository is built on ONE session handed in by the caller — under the
real app, that session comes from `infra/database/session.get_db_session`, and
its lifetime is the whole HTTP request, not one repository call. That is what
makes a request a Unit of Work: two repository calls in the same request share
the same transaction, so if the second one fails, the first one's work rolls
back too, instead of already being committed.

Because of that, methods here only ever `flush()`, never `commit()` or open
their own transaction. `flush()` still sends the SQL to Postgres immediately —
so an IntegrityError still surfaces exactly where it always did, at the point
of the operation, which is what keeps `errors.translate()` working unchanged —
it just doesn't end the transaction. The commit happens exactly once, at the
end of the request, in `get_db_session`.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional, Sequence, Tuple, Type, TypeVar

from sqlalchemy import func, select, update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import translate
from ..interfaces.common import Page

R = TypeVar("R")


class PostgresRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _fetch_one(self, model: Type[Any], *where: Any) -> Optional[Any]:
        result = await self._session.execute(select(model).where(*where))
        return result.scalar_one_or_none()

    async def _fetch_page(
        self, model: Type[Any], *where: Any, limit: int, offset: int
    ) -> Tuple[Sequence[Any], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(model).where(*where)
        )
        # The tie-break on id is what makes an offset page stable when two
        # rows share a created_at.
        rows = await self._session.execute(
            select(model)
            .where(*where)
            .order_by(model.created_at.desc(), model.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return rows.scalars().all(), int(total or 0)

    async def _insert(self, model: Type[Any], values: Dict[str, Any]) -> Any:
        try:
            row = model(**values)
            self._session.add(row)
            await self._session.flush()
            await self._session.refresh(row)
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
            if changes:
                changes["updated_at"] = dt.datetime.now(dt.timezone.utc)
                await self._session.execute(sql_update(model).where(where).values(**changes))
            result = await self._session.execute(select(model).where(where))
            return result.scalar_one_or_none()
        except IntegrityError as error:
            raise translate(error, values=changes) from error


def page_of(items, total: int, limit: int, offset: int) -> Page:
    return Page(items=list(items), total=total, limit=limit, offset=offset)
