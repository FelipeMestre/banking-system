"""Contract for `card_account_admin_actions` persistence (D1/D2).

`typing.Protocol`, matching this codebase's real convention (see
`card_account_repository.py`'s own docstring on the same point).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ICardAccountAdminActionRepository(Protocol):
    async def record(
        self,
        *,
        card_account_id: UUID,
        action: str,
        admin_id: str,
        reason: str | None,
        details: dict | None,
    ) -> None:
        """Insert one audit row in the caller's own `DbSession` and `flush()`
        it (design D1/D2) — never its own commit, never Kafka. Rolls back
        with the rest of the request's Unit of Work if anything later in the
        same request fails."""
        ...
