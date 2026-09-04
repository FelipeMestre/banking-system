"""In-memory doubles for every outbound port.

The whole API surface is exercised without a broker, a database or Redis. That
is only possible because every dependency is a port; if a controller reached for
asyncpg directly none of this would work.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from openbankapi.domain.exceptions import (
    DuplicateAccountNumberError,
    DuplicateCardNumberError,
    DuplicateError,
    ReferencedEntityNotFoundError,
)
from openbankapi.domain.model import (
    Account,
    AccountStatus,
    Branch,
    Card,
    CardAccount,
    CardAccountStatus,
    CardStatus,
    Customer,
    Location,
    Transaction,
    TransactionType,
)
from openbankapi.infra.database.interfaces.common import Page


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class FakePublisher:
    def __init__(self):
        self.published: List[tuple] = []

    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        self.published.append((topic, key, value))


class FakeCache:
    """Counts hits and misses so cache-aside can actually be asserted."""

    def __init__(self, *, failing: bool = False, store: Optional[Dict[str, Any]] = None):
        self.store: Dict[str, Any] = store if store is not None else {}
        self.failing = failing
        self.gets = 0
        self.get_calls: List[str] = []
        self.set_calls: List[tuple[str, Any, int]] = []
        self.deletes: List[str] = []
        self.ttls: Dict[str, int] = {}

    async def get(self, key: str):
        self.gets += 1
        self.get_calls.append(key)
        if self.failing:
            return None  # a broken cache degrades to a miss, never an error
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        self.set_calls.append((key, value, ttl_seconds))
        self.ttls[key] = ttl_seconds
        if not self.failing:
            self.store[key] = value

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.store.pop(key, None)

    async def close(self) -> None:
        return None


class FakeLocationRepository:
    def __init__(self):
        self.rows: Dict[UUID, Location] = {}
        self.loads = 0

    async def create(self, *, name: str) -> Location:
        entity = Location(id=uuid.uuid4(), name=name, active=True, created_at=_now(), updated_at=_now())
        self.rows[entity.id] = entity
        return entity

    async def get(self, location_id: UUID) -> Optional[Location]:
        self.loads += 1
        return self.rows.get(location_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(
        self, location_id: UUID, *, name: Optional[str] = None, active: Optional[bool] = None
    ) -> Optional[Location]:
        current = self.rows.get(location_id)
        if current is None:
            return None
        updated = Location(
            id=current.id,
            name=name if name is not None else current.name,
            active=current.active if active is None else active,
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[location_id] = updated
        return updated

    async def deactivate(self, location_id: UUID) -> Optional[Location]:
        return await self.update(location_id, active=False)


class FakeBranchRepository:
    def __init__(self, *, known_locations: Optional[set] = None):
        self.rows: Dict[UUID, Branch] = {}
        self.known_locations = known_locations if known_locations is not None else set()
        self.codes: set = set()

    async def create(self, *, code: str, name: str, location_id: UUID) -> Branch:
        # Stands in for the FK: the real repository lets Postgres decide and
        # translates the violation, but the domain error is the same.
        if location_id not in self.known_locations:
            raise ReferencedEntityNotFoundError("location_id", location_id)
        if code in self.codes:
            raise DuplicateError("code", code)
        self.codes.add(code)
        entity = Branch(id=uuid.uuid4(), code=code, name=name,
                          location_id=location_id, active=True,
                          created_at=_now(), updated_at=_now())
        self.rows[entity.id] = entity
        return entity

    async def get(self, branch_id: UUID) -> Optional[Branch]:
        return self.rows.get(branch_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, branch_id: UUID, **changes) -> Optional[Branch]:
        current = self.rows.get(branch_id)
        if current is None:
            return None
        updated = Branch(
            id=current.id,
            code=changes.get("code") or current.code,
            name=changes.get("name") or current.name,
            location_id=changes.get("location_id") or current.location_id,
            active=current.active if changes.get("active") is None else changes["active"],
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[branch_id] = updated
        return updated

    async def deactivate(self, branch_id: UUID) -> Optional[Branch]:
        return await self.update(branch_id, active=False)

    async def get_oldest_active(self) -> Optional[Branch]:
        # `min` returns the first element on a tie, and `self.rows.values()`
        # iterates in insertion order — that is the fake's tie-break.
        active = [branch for branch in self.rows.values() if branch.active]
        if not active:
            return None
        return min(active, key=lambda branch: branch.created_at)


class FakeCustomerRepository:
    def __init__(self):
        self.rows: Dict[UUID, Customer] = {}

    async def create(self, **kwargs) -> Customer:
        sub = kwargs.get("auth0_sub")
        if sub is not None and any(c.auth0_sub == sub for c in self.rows.values()):
            # Stands in for the real UNIQUE(auth0_sub) violation (translated
            # via errors.py's `_UNIQUE_KEYS`): simulates a lost race where
            # another request created the Customer between the caller's
            # existence check and this insert (amendment).
            raise DuplicateError("auth0_sub", sub)
        entity = Customer(id=uuid.uuid4(), active=True, created_at=_now(),
                         updated_at=_now(), **kwargs)
        self.rows[entity.id] = entity
        return entity

    async def get(self, customer_id: UUID) -> Optional[Customer]:
        return self.rows.get(customer_id)

    async def get_by_auth0_sub(self, sub: str) -> Optional[Customer]:
        return next((c for c in self.rows.values() if c.auth0_sub == sub), None)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, customer_id: UUID, **changes) -> Optional[Customer]:
        current = self.rows.get(customer_id)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Customer(
            id=current.id,
            identification_number=supplied.get("identification_number", current.identification_number),
            first_name=supplied.get("first_name", current.first_name),
            last_name=supplied.get("last_name", current.last_name),
            date_of_birth=supplied.get("date_of_birth", current.date_of_birth),
            gender=supplied.get("gender", current.gender),
            active=supplied.get("active", current.active),
            auth0_sub=supplied.get("auth0_sub", current.auth0_sub),
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[customer_id] = updated
        return updated

    async def deactivate(self, customer_id: UUID) -> Optional[Customer]:
        return await self.update(customer_id, active=False)


class FakeAccountRepository:
    """Also plays the balance projection, so a test can watch both sides."""

    def __init__(self, *, known_customers=None, known_branches=None, collide_times: int = 0):
        self.rows: Dict[str, Account] = {}
        self.known_customers = known_customers if known_customers is not None else set()
        self.known_branches = known_branches if known_branches is not None else set()
        self.collide_times = collide_times
        self.attempts = 0

    async def create(self, *, currency: str, customer_id: UUID, branch_id: UUID) -> Account:
        if customer_id not in self.known_customers:
            raise ReferencedEntityNotFoundError("customer_id", customer_id)
        if branch_id not in self.known_branches:
            raise ReferencedEntityNotFoundError("branch_id", branch_id)
        from openbankapi.infra.database.repositories import generate_account_number

        for _ in range(5):
            self.attempts += 1
            account_number = generate_account_number()
            if self.collide_times > 0:
                self.collide_times -= 1
                continue  # simulate the UNIQUE violation the real repo retries
            entity = Account(id=uuid.uuid4(), account_number=account_number, currency=currency,
                            customer_id=customer_id, branch_id=branch_id, balance=0,
                            status=AccountStatus.ACTIVE, created_at=_now(), updated_at=_now())
            self.rows[account_number] = entity
            return entity
        raise DuplicateAccountNumberError("exhausted")

    async def get_by_account_number(self, account_number: str) -> Optional[Account]:
        return self.rows.get(account_number)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, account_number: str, **changes) -> Optional[Account]:
        assert "balance" not in changes, "balance must never reach the repository"
        current = self.rows.get(account_number)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Account(
            id=current.id, account_number=current.account_number,
            currency=supplied.get("currency", current.currency),
            customer_id=current.customer_id,
            branch_id=supplied.get("branch_id", current.branch_id),
            balance=current.balance,  # never from the caller
            status=AccountStatus(supplied.get("status", current.status.value)),
            created_at=current.created_at, updated_at=_now(),
        )
        self.rows[account_number] = updated
        return updated

    async def close(self, account_number: str) -> Optional[Account]:
        return await self.update(account_number, status="closed")

    async def has_nonempty_account_for_customer(self, customer_id: UUID) -> bool:
        return any(
            account.customer_id == customer_id
            and account.status is AccountStatus.ACTIVE
            and account.balance != 0
            for account in self.rows.values()
        )

    async def has_active_account_for_branch(self, branch_id: UUID) -> bool:
        return any(
            account.branch_id == branch_id and account.status is AccountStatus.ACTIVE
            for account in self.rows.values()
        )

    async def apply_balance(self, account_number: str, balance: int) -> bool:
        current = self.rows.get(account_number)
        if current is None:
            return False
        self.rows[account_number] = Account(
            id=current.id, account_number=current.account_number, currency=current.currency,
            customer_id=current.customer_id, branch_id=current.branch_id,
            balance=balance, status=current.status,
            created_at=current.created_at, updated_at=_now(),
        )
        return True

    async def list_by_customer(self, customer_id: UUID, *, limit: int, offset: int) -> Page:
        items = [a for a in self.rows.values() if a.customer_id == customer_id][offset : offset + limit]
        total = sum(1 for a in self.rows.values() if a.customer_id == customer_id)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def has_any_account_for_customer(self, customer_id: UUID) -> bool:
        return any(account.customer_id == customer_id for account in self.rows.values())

    async def lock_customer_for_account_creation(self, customer_id: UUID) -> None:
        """No-op here: the fake test suite runs single-threaded (`asyncio.run`
        per scenario), so there is no concurrent session to block against.
        The real advisory lock only matters under genuine Postgres concurrency."""
        return None

    async def lock_identity_for_account_creation(self, auth0_sub: str) -> None:
        """No-op, same rationale as `lock_customer_for_account_creation` above
        (amendment — never-linked-identity path)."""
        return None


class FakeTransactionRepository:
    """Identity is `(request_id, account_number, type)` — the same tuple the
    real `UNIQUE` constraint and `ON CONFLICT DO NOTHING` enforce (spec §3.2).
    """

    def __init__(self):
        self.rows: List[Transaction] = []
        self._seen: set = set()

    async def insert(
        self,
        *,
        request_id: UUID,
        account_number: str,
        type: str,
        amount: int,
        counterparty_account: str,
        decline_reason: Optional[str],
        ts: dt.datetime,
        applied_rate_id: Optional[UUID] = None,
    ) -> None:
        key = (request_id, account_number, type)
        if key in self._seen:
            return
        self._seen.add(key)
        self.rows.append(
            Transaction(
                id=uuid.uuid4(), request_id=request_id, account_number=account_number,
                type=TransactionType(type), amount=amount,
                counterparty_account=counterparty_account, decline_reason=decline_reason, ts=ts,
                applied_rate_id=applied_rate_id,
            )
        )

    async def list_by_account(
        self, account_number: str, *, limit: int, before: Optional[tuple] = None
    ) -> List[Transaction]:
        candidates = [row for row in self.rows if row.account_number == account_number]
        if before is not None:
            before_ts, before_id = before
            candidates = [
                row for row in candidates
                if (row.ts, row.id) < (before_ts, before_id)
            ]
        candidates.sort(key=lambda row: (row.ts, row.id), reverse=True)
        return candidates[:limit]


class FakeAppliedRateRepository:
    """In-memory double for IAppliedRateRepository (FX-16)."""

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    async def insert(
        self,
        *,
        pair: str,
        mid_rate: float,
        applied_rate: float,
        margin: float,
        direction: str,
        source_ts: dt.datetime,
    ) -> str:
        new_id = uuid.uuid4()
        self.rows.append(
            {
                "id": new_id,
                "pair": pair,
                "mid_rate": mid_rate,
                "applied_rate": applied_rate,
                "margin": margin,
                "direction": direction,
                "source_ts": source_ts,
            }
        )
        return str(new_id)


class FakeCardAccountRepository:
    """In-memory double for ICardAccountRepository (Credit Cards Phase 1)."""

    def __init__(self, *, known_customers=None, known_accounts=None):
        self.rows: Dict[UUID, CardAccount] = {}
        self.known_customers = known_customers if known_customers is not None else set()
        self.known_accounts = known_accounts if known_accounts is not None else set()
        self.create_calls = 0

    async def create(self, *, customer_id, paying_account_id, credit_limit) -> CardAccount:
        self.create_calls += 1
        if customer_id not in self.known_customers:
            raise ReferencedEntityNotFoundError("customer_id", customer_id)
        if paying_account_id not in self.known_accounts:
            raise ReferencedEntityNotFoundError("paying_account_id", paying_account_id)
        entity = CardAccount(
            id=uuid.uuid4(), customer_id=customer_id, paying_account_id=paying_account_id,
            credit_limit=credit_limit, status=CardAccountStatus.ACTIVE,
            created_at=_now(), updated_at=_now(),
        )
        self.rows[entity.id] = entity
        return entity

    async def get_by_id(self, card_account_id: UUID) -> Optional[CardAccount]:
        return self.rows.get(card_account_id)

    async def list_by_customer(self, customer_id: UUID, *, limit: int, offset: int) -> Page:
        items = [a for a in self.rows.values() if a.customer_id == customer_id][offset : offset + limit]
        total = sum(1 for a in self.rows.values() if a.customer_id == customer_id)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def update_status(self, card_account_id: UUID, *, status: str) -> Optional[CardAccount]:
        current = self.rows.get(card_account_id)
        if current is None:
            return None
        updated = CardAccount(
            id=current.id, customer_id=current.customer_id,
            paying_account_id=current.paying_account_id, credit_limit=current.credit_limit,
            status=CardAccountStatus(status), created_at=current.created_at, updated_at=_now(),
        )
        self.rows[card_account_id] = updated
        return updated

    async def update_limit(self, card_account_id: UUID, *, credit_limit) -> Optional[CardAccount]:
        current = self.rows.get(card_account_id)
        if current is None:
            return None
        updated = CardAccount(
            id=current.id, customer_id=current.customer_id,
            paying_account_id=current.paying_account_id, credit_limit=credit_limit,
            status=current.status, created_at=current.created_at, updated_at=_now(),
        )
        self.rows[card_account_id] = updated
        return updated


class FakeCardRepository:
    """In-memory double for ICardRepository (Credit Cards Phase 1)."""

    def __init__(self, *, collide_times: int = 0):
        self.rows: Dict[UUID, Card] = {}
        self.by_number: Dict[str, UUID] = {}
        self.collide_times = collide_times
        self.attempts = 0

    async def create(self, *, card_account_id, expiration_date) -> Card:
        from openbankapi.infra.database.repositories import generate_card_number

        for _ in range(5):
            self.attempts += 1
            card_number = generate_card_number()
            if self.collide_times > 0 or card_number in self.by_number:
                self.collide_times = max(0, self.collide_times - 1)
                continue
            entity = Card(
                id=uuid.uuid4(), card_account_id=card_account_id, card_number=card_number,
                expiration_date=expiration_date, status=CardStatus.ACTIVE,
                created_at=_now(), updated_at=_now(),
            )
            self.rows[entity.id] = entity
            self.by_number[card_number] = entity.id
            return entity
        raise DuplicateCardNumberError("exhausted")

    async def get_by_number(self, card_number: str) -> Optional[Card]:
        card_id = self.by_number.get(card_number)
        return self.rows.get(card_id) if card_id else None

    async def get_active_for_account(self, card_account_id: UUID) -> Optional[Card]:
        return next(
            (c for c in self.rows.values() if c.card_account_id == card_account_id and c.is_active),
            None,
        )

    async def mark_replaced(self, card_id: UUID) -> Optional[Card]:
        return await self._set_status(card_id, CardStatus.REPLACED)

    async def update_status(self, card_id: UUID, *, status: str) -> Optional[Card]:
        return await self._set_status(card_id, CardStatus(status))

    async def _set_status(self, card_id: UUID, status: CardStatus) -> Optional[Card]:
        current = self.rows.get(card_id)
        if current is None:
            return None
        updated = Card(
            id=current.id, card_account_id=current.card_account_id,
            card_number=current.card_number, expiration_date=current.expiration_date,
            status=status, created_at=current.created_at, updated_at=_now(),
        )
        self.rows[card_id] = updated
        return updated


class FakeForeignExchangeRepository:
    """Fake for IForeignExchangeRepository — counts calls, returns fixed mids."""

    def __init__(
        self,
        rates: Optional[Dict[str, float]] = None,
        raise_error: Optional[Exception] = None,
    ):
        self.rates: Dict[str, float] = rates if rates is not None else {"EUR": 0.8613, "GBP": 0.74}
        self.raise_error = raise_error
        self.calls = 0

    async def get_all_mid_rates(self) -> Dict[str, float]:
        self.calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        return dict(self.rates)
