"""Shared DTO pieces."""
from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

from ....infra.database.interfaces.common import DEFAULT_LIMIT, MAX_LIMIT

T = TypeVar("T")


class PageParams(BaseModel):
    """Bounded paging. An unbounded list endpoint is a table scan waiting to happen."""

    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class PageResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
