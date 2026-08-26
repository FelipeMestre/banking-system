"""Shared paging types for the repository contracts.

The spec is silent on pagination, so this fixes one convention: limit/offset
with a bounded limit and a stable `created_at DESC, id DESC` ordering. Unbounded
list endpoints are how a prototype becomes a full table scan in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(frozen=True)
class Page(Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
