"""Contract for `card_accounts` persistence.

`typing.Protocol`, not `abc.ABC` — matches this codebase's real convention
(`IAccountRepository`, `IAppliedRateRepository`), not the ABC wording in the
raw user spec text (same precedent documented in `applied_rate_repository.py`).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional, Protocol, Union, runtime_checkable
from uuid import UUID

from ....domain.model import CardAccount
from .common import Page


@runtime_checkable
class ICardAccountRepository(Protocol):
    async def create(
        self, *, customer_id: UUID, paying_account_id: UUID, credit_limit: Union[int, Decimal]
    ) -> CardAccount:
        """Create a card account. Status defaults to `active`."""
        ...

    async def get_by_id(self, card_account_id: UUID) -> Optional[CardAccount]: ...

    async def list_by_customer(
        self, customer_id: UUID, *, limit: int, offset: int
    ) -> Page[CardAccount]: ...

    async def update_status(self, card_account_id: UUID, *, status: str) -> Optional[CardAccount]:
        """Set `status` unconditionally — the caller must validate the
        transition against `CARD_ACCOUNT_TRANSITIONS` before calling this."""
        ...

    async def update_limit(
        self, card_account_id: UUID, *, credit_limit: Union[int, Decimal]
    ) -> Optional[CardAccount]: ...

    async def list_active_ids(self) -> List[UUID]:
        """Every `card_account` still billable — `status != 'closed'` — the
        batch worker's iteration set (Credit Cards Phase 4). A BLOCKED
        account still has an outstanding balance and must keep getting
        statements; blocking only affects Phase 2's purchase check, not
        this billing phase. Only a CLOSED account has no ongoing credit
        line and is excluded."""
        ...

    async def get_issuance_date(self, card_account_id: UUID) -> date:
        """`created_at` as a date — no separate issuance-date concept exists."""
        ...
