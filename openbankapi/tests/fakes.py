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
    DuplicateError,
    ReferencedEntityNotFoundError,
)
from openbankapi.domain.model import Customer, Account, AccountStatus, Location, Branch
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

    def __init__(self, *, failing: bool = False):
        self.store: Dict[str, Any] = {}
        self.failing = failing
        self.gets = 0
        self.deletes: List[str] = []

    async def get(self, key: str):
        self.gets += 1
        if self.failing:
            return None  # a broken cache degrades to a miss, never an error
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
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
        entity = Location(id=uuid.uuid4(), name=name, created_at=_now(), updated_at=_now())
        self.rows[entity.id] = entity
        return entity

    async def get(self, location_id: UUID) -> Optional[Location]:
        self.loads += 1
        return self.rows.get(location_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, location_id: UUID, *, name: Optional[str]) -> Optional[Location]:
        current = self.rows.get(location_id)
        if current is None:
            return None
        updated = Location(id=current.id, name=name or current.name,
                           created_at=current.created_at, updated_at=_now())
        self.rows[location_id] = updated
        return updated


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


class FakeCustomerRepository:
    def __init__(self):
        self.rows: Dict[UUID, Customer] = {}

    async def create(self, **kwargs) -> Customer:
        entity = Customer(id=uuid.uuid4(), active=True, created_at=_now(),
                         updated_at=_now(), **kwargs)
        self.rows[entity.id] = entity
        return entity

    async def get(self, customer_id: UUID) -> Optional[Customer]:
        return self.rows.get(customer_id)

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
            name=supplied.get("name", current.name),
            last_name=supplied.get("last_name", current.last_name),
            date_of_birth=supplied.get("date_of_birth", current.date_of_birth),
            gender=supplied.get("gender", current.gender),
            active=supplied.get("active", current.active),
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
