"""In-memory doubles for every outbound port.

The whole API surface is exercised without a broker, a database or Redis. That
is only possible because every dependency is a port; if a controller reached for
asyncpg directly none of this would work.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any
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
    AppliedRate,
    Branch,
    Card,
    CardAccount,
    CardAccountStatus,
    CardMovement,
    CardMovementType,
    CardStatus,
    Customer,
    Installment,
    Location,
    Statement,
    StatementStatus,
    Transaction,
    TransactionType,
)
from openbankapi.infra.database.interfaces.common import Page


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class FakePublisher:
    def __init__(self):
        self.published: list[tuple] = []

    def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.published.append((topic, key, value))


class FakeCache:
    """Counts hits and misses so cache-aside can actually be asserted."""

    def __init__(self, *, failing: bool = False, store: dict[str, Any] | None = None):
        self.store: dict[str, Any] = store if store is not None else {}
        self.failing = failing
        self.gets = 0
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, Any, int]] = []
        self.deletes: list[str] = []
        self.ttls: dict[str, int] = {}

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
        self.rows: dict[UUID, Location] = {}
        self.loads = 0

    async def create(self, *, name: str) -> Location:
        entity = Location(
            id=uuid.uuid4(),
            name=name,
            active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        self.rows[entity.id] = entity
        return entity

    async def get(self, location_id: UUID) -> Location | None:
        self.loads += 1
        return self.rows.get(location_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(
        self, location_id: UUID, *, name: str | None = None, active: bool | None = None
    ) -> Location | None:
        current = self.rows.get(location_id)
        if current is None:
            return None
        updated = Location(
            id=current.id,
            name=name if name is not None else current.name,
            active=current.active if active is None else active,
            created_at=current.created_at,
            updated_at=_now(),
        )
        self.rows[location_id] = updated
        return updated

    async def deactivate(self, location_id: UUID) -> Location | None:
        return await self.update(location_id, active=False)


class FakeBranchRepository:
    def __init__(self, *, known_locations: set | None = None):
        self.rows: dict[UUID, Branch] = {}
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
        entity = Branch(
            id=uuid.uuid4(),
            code=code,
            name=name,
            location_id=location_id,
            active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        self.rows[entity.id] = entity
        return entity

    async def get(self, branch_id: UUID) -> Branch | None:
        return self.rows.get(branch_id)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, branch_id: UUID, **changes) -> Branch | None:
        current = self.rows.get(branch_id)
        if current is None:
            return None
        updated = Branch(
            id=current.id,
            code=changes.get("code") or current.code,
            name=changes.get("name") or current.name,
            location_id=changes.get("location_id") or current.location_id,
            active=current.active
            if changes.get("active") is None
            else changes["active"],
            created_at=current.created_at,
            updated_at=_now(),
        )
        self.rows[branch_id] = updated
        return updated

    async def deactivate(self, branch_id: UUID) -> Branch | None:
        return await self.update(branch_id, active=False)

    async def get_oldest_active(self) -> Branch | None:
        # `min` returns the first element on a tie, and `self.rows.values()`
        # iterates in insertion order — that is the fake's tie-break.
        active = [branch for branch in self.rows.values() if branch.active]
        if not active:
            return None
        return min(active, key=lambda branch: branch.created_at)


class FakeCustomerRepository:
    def __init__(self):
        self.rows: dict[UUID, Customer] = {}

    async def create(self, **kwargs) -> Customer:
        sub = kwargs.get("auth0_sub")
        if sub is not None and any(c.auth0_sub == sub for c in self.rows.values()):
            # Stands in for the real UNIQUE(auth0_sub) violation (translated
            # via errors.py's `_UNIQUE_KEYS`): simulates a lost race where
            # another request created the Customer between the caller's
            # existence check and this insert (amendment).
            raise DuplicateError("auth0_sub", sub)
        entity = Customer(
            id=uuid.uuid4(), active=True, created_at=_now(), updated_at=_now(), **kwargs
        )
        self.rows[entity.id] = entity
        return entity

    async def get(self, customer_id: UUID) -> Customer | None:
        return self.rows.get(customer_id)

    async def get_by_auth0_sub(self, sub: str) -> Customer | None:
        return next((c for c in self.rows.values() if c.auth0_sub == sub), None)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, customer_id: UUID, **changes) -> Customer | None:
        current = self.rows.get(customer_id)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Customer(
            id=current.id,
            identification_number=supplied.get(
                "identification_number", current.identification_number
            ),
            first_name=supplied.get("first_name", current.first_name),
            last_name=supplied.get("last_name", current.last_name),
            date_of_birth=supplied.get("date_of_birth", current.date_of_birth),
            gender=supplied.get("gender", current.gender),
            active=supplied.get("active", current.active),
            auth0_sub=supplied.get("auth0_sub", current.auth0_sub),
            created_at=current.created_at,
            updated_at=_now(),
        )
        self.rows[customer_id] = updated
        return updated

    async def deactivate(self, customer_id: UUID) -> Customer | None:
        return await self.update(customer_id, active=False)


class FakeAccountRepository:
    """Also plays the balance projection, so a test can watch both sides."""

    def __init__(
        self, *, known_customers=None, known_branches=None, collide_times: int = 0
    ):
        self.rows: dict[str, Account] = {}
        self.known_customers = known_customers if known_customers is not None else set()
        self.known_branches = known_branches if known_branches is not None else set()
        self.collide_times = collide_times
        self.attempts = 0

    async def create(
        self, *, currency: str, customer_id: UUID, branch_id: UUID
    ) -> Account:
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
            entity = Account(
                id=uuid.uuid4(),
                account_number=account_number,
                currency=currency,
                customer_id=customer_id,
                branch_id=branch_id,
                balance=0,
                status=AccountStatus.ACTIVE,
                created_at=_now(),
                updated_at=_now(),
            )
            self.rows[account_number] = entity
            return entity
        raise DuplicateAccountNumberError("exhausted")

    async def get_by_account_number(self, account_number: str) -> Account | None:
        return self.rows.get(account_number)

    async def get_by_id(self, account_id: UUID) -> Account | None:
        return next((row for row in self.rows.values() if row.id == account_id), None)

    async def list(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def update(self, account_number: str, **changes) -> Account | None:
        assert "balance" not in changes, "balance must never reach the repository"
        current = self.rows.get(account_number)
        if current is None:
            return None
        supplied = {k: v for k, v in changes.items() if v is not None}
        updated = Account(
            id=current.id,
            account_number=current.account_number,
            currency=supplied.get("currency", current.currency),
            customer_id=current.customer_id,
            branch_id=supplied.get("branch_id", current.branch_id),
            balance=current.balance,  # never from the caller
            status=AccountStatus(supplied.get("status", current.status.value)),
            created_at=current.created_at,
            updated_at=_now(),
        )
        self.rows[account_number] = updated
        return updated

    async def close(self, account_number: str) -> Account | None:
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
            id=current.id,
            account_number=current.account_number,
            currency=current.currency,
            customer_id=current.customer_id,
            branch_id=current.branch_id,
            balance=balance,
            status=current.status,
            created_at=current.created_at,
            updated_at=_now(),
        )
        return True

    async def list_by_customer(
        self, customer_id: UUID, *, limit: int, offset: int
    ) -> Page:
        items = [a for a in self.rows.values() if a.customer_id == customer_id][
            offset : offset + limit
        ]
        total = sum(1 for a in self.rows.values() if a.customer_id == customer_id)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def has_any_account_for_customer(self, customer_id: UUID) -> bool:
        return any(account.customer_id == customer_id for account in self.rows.values())

    async def lock_customer_for_account_creation(self, customer_id: UUID) -> None:
        """No-op here: the fake test suite runs single-threaded (`asyncio.run`
        per scenario), so there is no concurrent session to block against.
        The real advisory lock only matters under genuine Postgres concurrency."""
        return

    async def lock_identity_for_account_creation(self, auth0_sub: str) -> None:
        """No-op, same rationale as `lock_customer_for_account_creation` above
        (amendment — never-linked-identity path)."""
        return


class FakeTransactionRepository:
    """Identity is `(request_id, account_number, type)` — the same tuple the
    real `UNIQUE` constraint and `ON CONFLICT DO NOTHING` enforce (spec §3.2).
    """

    def __init__(self):
        self.rows: list[Transaction] = []
        self._seen: set = set()

    async def insert(
        self,
        *,
        request_id: UUID,
        account_number: str,
        type: str,
        amount: int,
        counterparty_account: str | None,
        decline_reason: str | None,
        ts: dt.datetime,
        applied_rate_id: UUID | None = None,
    ) -> UUID | None:
        key = (request_id, account_number, type)
        if key in self._seen:
            return None
        self._seen.add(key)
        new_id = uuid.uuid4()
        self.rows.append(
            Transaction(
                id=new_id,
                request_id=request_id,
                account_number=account_number,
                type=TransactionType(type),
                amount=amount,
                counterparty_account=counterparty_account,
                decline_reason=decline_reason,
                ts=ts,
                applied_rate_id=applied_rate_id,
            )
        )
        return new_id

    async def set_applied_rate(
        self, transaction_id: UUID, applied_rate_id: UUID
    ) -> None:
        for idx, row in enumerate(self.rows):
            if row.id == transaction_id:
                self.rows[idx] = Transaction(
                    id=row.id,
                    request_id=row.request_id,
                    account_number=row.account_number,
                    type=row.type,
                    amount=row.amount,
                    counterparty_account=row.counterparty_account,
                    decline_reason=row.decline_reason,
                    ts=row.ts,
                    applied_rate_id=applied_rate_id,
                )
                return

    async def list_by_account(
        self, account_number: str, *, limit: int, before: tuple | None = None
    ) -> list[Transaction]:
        candidates = [row for row in self.rows if row.account_number == account_number]
        if before is not None:
            before_ts, before_id = before
            candidates = [
                row for row in candidates if (row.ts, row.id) < (before_ts, before_id)
            ]
        candidates.sort(key=lambda row: (row.ts, row.id), reverse=True)
        return candidates[:limit]


class FakeAppliedRateRepository:
    """In-memory double for IAppliedRateRepository (FX-16)."""

    def __init__(self):
        self.rows: list[dict[str, Any]] = []

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

    async def get_by_id(self, applied_rate_id: UUID) -> AppliedRate | None:
        row = next((r for r in self.rows if r["id"] == applied_rate_id), None)
        if row is None:
            return None
        return AppliedRate(
            id=row["id"],
            pair=row["pair"],
            mid_rate=row["mid_rate"],
            applied_rate=row["applied_rate"],
            margin=row["margin"],
            direction=row["direction"],
            source_ts=row["source_ts"],
            created_at=row["source_ts"],
        )


class FakeCardAccountRepository:
    """In-memory double for ICardAccountRepository (Credit Cards Phase 1)."""

    def __init__(self, *, known_customers=None, known_accounts=None):
        self.rows: dict[UUID, CardAccount] = {}
        self.known_customers = known_customers if known_customers is not None else set()
        self.known_accounts = known_accounts if known_accounts is not None else set()
        self.create_calls = 0

    async def create(
        self, *, customer_id, paying_account_id, credit_limit
    ) -> CardAccount:
        self.create_calls += 1
        if customer_id not in self.known_customers:
            raise ReferencedEntityNotFoundError("customer_id", customer_id)
        if paying_account_id not in self.known_accounts:
            raise ReferencedEntityNotFoundError("paying_account_id", paying_account_id)
        entity = CardAccount(
            id=uuid.uuid4(),
            customer_id=customer_id,
            paying_account_id=paying_account_id,
            credit_limit=credit_limit,
            status=CardAccountStatus.ACTIVE,
            created_at=_now(),
            updated_at=_now(),
            used_credit=0,
        )
        self.rows[entity.id] = entity
        return entity

    async def get_by_id(self, card_account_id: UUID) -> CardAccount | None:
        return self.rows.get(card_account_id)

    async def list_by_customer(
        self, customer_id: UUID, *, limit: int, offset: int
    ) -> Page:
        items = [a for a in self.rows.values() if a.customer_id == customer_id][
            offset : offset + limit
        ]
        total = sum(1 for a in self.rows.values() if a.customer_id == customer_id)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def update_status(
        self, card_account_id: UUID, *, status: str
    ) -> CardAccount | None:
        current = self.rows.get(card_account_id)
        if current is None:
            return None
        updated = CardAccount(
            id=current.id,
            customer_id=current.customer_id,
            paying_account_id=current.paying_account_id,
            credit_limit=current.credit_limit,
            status=CardAccountStatus(status),
            created_at=current.created_at,
            updated_at=_now(),
            used_credit=current.used_credit,
        )
        self.rows[card_account_id] = updated
        return updated

    async def update_limit(
        self, card_account_id: UUID, *, credit_limit
    ) -> CardAccount | None:
        current = self.rows.get(card_account_id)
        if current is None:
            return None
        updated = CardAccount(
            id=current.id,
            customer_id=current.customer_id,
            paying_account_id=current.paying_account_id,
            credit_limit=credit_limit,
            status=current.status,
            created_at=current.created_at,
            updated_at=_now(),
            used_credit=current.used_credit,
        )
        self.rows[card_account_id] = updated
        return updated

    async def apply_used_credit(self, card_account_id: UUID, used_credit: int) -> bool:
        current = self.rows.get(card_account_id)
        if current is None:
            return False
        self.rows[card_account_id] = CardAccount(
            id=current.id, customer_id=current.customer_id,
            paying_account_id=current.paying_account_id, credit_limit=current.credit_limit,
            status=current.status, created_at=current.created_at, updated_at=_now(),
            used_credit=used_credit,
        )
        return True

    async def list_active_ids(self) -> List[UUID]:
        """Every card_account still billable — everything except CLOSED
        (Credit Cards Phase 4 correction: a BLOCKED account still has an
        outstanding balance and must keep getting statements; blocking only
        affects Phase 2's purchase check, not this phase)."""
        return [
            row.id
            for row in self.rows.values()
            if row.status is not CardAccountStatus.CLOSED
        ]

    async def get_issuance_date(self, card_account_id: UUID):
        row = self.rows.get(card_account_id)
        return row.created_at.date() if row is not None else None


class FakeCardRepository:
    """In-memory double for ICardRepository (Credit Cards Phase 1)."""

    def __init__(self, *, collide_times: int = 0):
        self.rows: dict[UUID, Card] = {}
        self.by_number: dict[str, UUID] = {}
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
                id=uuid.uuid4(),
                card_account_id=card_account_id,
                card_number=card_number,
                expiration_date=expiration_date,
                status=CardStatus.ACTIVE,
                created_at=_now(),
                updated_at=_now(),
            )
            self.rows[entity.id] = entity
            self.by_number[card_number] = entity.id
            return entity
        raise DuplicateCardNumberError("exhausted")

    async def get_by_number(self, card_number: str) -> Card | None:
        card_id = self.by_number.get(card_number)
        return self.rows.get(card_id) if card_id else None

    async def list_all(self, *, limit: int, offset: int) -> Page:
        items = list(self.rows.values())[offset : offset + limit]
        return Page(items=items, total=len(self.rows), limit=limit, offset=offset)

    async def get_active_for_account(self, card_account_id: UUID) -> Card | None:
        return next(
            (
                c
                for c in self.rows.values()
                if c.card_account_id == card_account_id and c.is_active
            ),
            None,
        )

    async def mark_replaced(self, card_id: UUID) -> Card | None:
        return await self._set_status(card_id, CardStatus.REPLACED)

    async def update_status(self, card_id: UUID, *, status: str) -> Card | None:
        return await self._set_status(card_id, CardStatus(status))

    async def _set_status(self, card_id: UUID, status: CardStatus) -> Card | None:
        current = self.rows.get(card_id)
        if current is None:
            return None
        updated = Card(
            id=current.id,
            card_account_id=current.card_account_id,
            card_number=current.card_number,
            expiration_date=current.expiration_date,
            status=status,
            created_at=current.created_at,
            updated_at=_now(),
        )
        self.rows[card_id] = updated
        return updated


class FakeForeignExchangeRepository:
    """Fake for IForeignExchangeRepository — counts calls, returns fixed mids."""

    def __init__(
        self,
        rates: dict[str, float] | None = None,
        raise_error: Exception | None = None,
    ):
        self.rates: dict[str, float] = (
            rates if rates is not None else {"EUR": 0.8613, "GBP": 0.74}
        )
        self.raise_error = raise_error
        self.calls = 0

    async def get_all_mid_rates(self) -> dict[str, float]:
        self.calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        return dict(self.rates)


class FakeCardMovementRepository:
    """In-memory double for `ICardMovementRepository` — Credit Cards Phase 2.

    Identity is `(request_id, movement_type)`, the same tuple the real
    `UNIQUE` constraint and `ON CONFLICT DO NOTHING` enforce.

    `cards` is a reference to the fake `ICardRepository` in use for this
    harness — resolving `card_account_id -> card_ids` mirrors the real
    Postgres `JOIN card_movements.card_id -> cards.id -> cards.card_account_id`
    instead of filtering movements directly (a movement row has no
    `card_account_id` column of its own, on Postgres or here).
    """

    def __init__(
        self,
        cards: FakeCardRepository | None = None,
        installments: FakeInstallmentRepository | None = None,
    ):
        self.rows: list[CardMovement] = []
        self._seen: set = set()
        self.cards = cards
        # Needed only by `sum_single_charge_purchases` to exclude
        # installment-plan purchases — mirrors the real repository's
        # `NOT EXISTS (SELECT 1 FROM installments WHERE card_movement_id = ...)`.
        self.installments = installments

    async def insert(self, movement: CardMovement) -> CardMovement:
        key = (movement.request_id, movement.movement_type)
        if key in self._seen:
            return next(
                row for row in self.rows if (row.request_id, row.movement_type) == key
            )
        self._seen.add(key)
        self.rows.append(movement)
        return movement

    async def get_by_card_account_id(self, card_account_id: UUID) -> list[CardMovement]:
        if self.cards is None:
            raise RuntimeError(
                "FakeCardMovementRepository.get_by_card_account_id needs a `cards` "
                "reference — construct with FakeCardMovementRepository(cards=...)."
            )
        card_ids = {
            card.id
            for card in self.cards.rows.values()
            if card.card_account_id == card_account_id
        }
        matches = [row for row in self.rows if row.card_id in card_ids]
        return sorted(matches, key=lambda row: row.created_at, reverse=True)

    def _card_ids_for(self, card_account_id: UUID) -> set:
        if self.cards is None:
            raise RuntimeError(
                "FakeCardMovementRepository aggregation methods need a `cards` "
                "reference — construct with FakeCardMovementRepository(cards=...)."
            )
        return {
            card.id
            for card in self.cards.rows.values()
            if card.card_account_id == card_account_id
        }

    def _in_period(self, row: CardMovement, period_start, period_end) -> bool:
        occurred = (row.occurred_at or row.created_at).date()
        return period_start <= occurred <= period_end

    async def sum_single_charge_purchases(
        self, card_account_id: UUID, period_start, period_end
    ) -> Decimal:
        """Purchases NOT part of an installment plan — excludes any movement
        whose id shows up as an `Installment.card_movement_id` anywhere."""
        card_ids = self._card_ids_for(card_account_id)
        installment_rows = (
            self.installments.rows if self.installments is not None else []
        )
        installment_movement_ids = {inst.card_movement_id for inst in installment_rows}
        total = Decimal(0)
        for row in self.rows:
            if (
                row.card_id in card_ids
                and row.movement_type == CardMovementType.PURCHASE
                and row.id not in installment_movement_ids
                and self._in_period(row, period_start, period_end)
            ):
                total += row.amount
        return total

    async def sum_by_type(
        self, card_account_id: UUID, movement_type: str, period_start, period_end
    ) -> Decimal:
        card_ids = self._card_ids_for(card_account_id)
        total = Decimal(0)
        for row in self.rows:
            if (
                row.card_id in card_ids
                and row.movement_type.value == movement_type
                and self._in_period(row, period_start, period_end)
            ):
                total += row.amount
        return total

    async def sum_payments(
        self, card_account_id: UUID, period_start, period_end
    ) -> Decimal:
        return await self.sum_by_type(
            card_account_id, CardMovementType.PAYMENT.value, period_start, period_end
        )


class FakeInstallmentRepository:
    """In-memory double for `IInstallmentRepository` — Credit Cards Phase 2."""

    def __init__(self):
        self.rows: list[Installment] = []

    async def bulk_insert(self, installments: list[Installment]) -> None:
        self.rows.extend(installments)

    async def get_by_movement_id(self, movement_id: UUID) -> list[Installment]:
        return [row for row in self.rows if row.card_movement_id == movement_id]

    async def get_by_statement_id(self, statement_id: UUID) -> list[Installment]:
        matches = [row for row in self.rows if row.statement_id == statement_id]
        return sorted(matches, key=lambda row: row.installment_number)

    async def sum_unbilled(self, card_account_id: UUID) -> Decimal:
        """Sum of `amount` across every unbilled installment (`statement_id
        is None`). Ignores `card_account_id` exactly like
        `get_next_due_per_plan` above does on this fake — every existing
        test scenario constructs one `FakeInstallmentRepository` per
        account, so there is nothing else in `self.rows` to wrongly
        include."""
        return sum(
            (row.amount for row in self.rows if row.statement_id is None), Decimal(0)
        )

    async def get_next_due_per_plan(
        self, card_account_id: UUID, card_ids: set | None = None
    ) -> list[Installment]:
        """Lowest unbilled `installment_number` per `card_movement_id`.

        `card_ids` is accepted so a caller/test can scope the plan search to
        one account's cards without the fake needing its own `cards`
        reference — mirrors what the real repository does via the
        `card_movements -> cards` join, done here by the caller supplying
        the relevant card_movement ids instead.
        """
        unbilled = [row for row in self.rows if row.statement_id is None]
        by_plan: dict[UUID, list[Installment]] = {}
        for row in unbilled:
            by_plan.setdefault(row.card_movement_id, []).append(row)
        result = []
        for plan_rows in by_plan.values():
            plan_rows.sort(key=lambda r: r.installment_number)
            result.append(plan_rows[0])
        return result

    async def mark_billed(self, installment_id: UUID, statement_id: UUID) -> None:
        for i, row in enumerate(self.rows):
            if row.id == installment_id:
                self.rows[i] = Installment(
                    id=row.id,
                    card_movement_id=row.card_movement_id,
                    installment_number=row.installment_number,
                    amount=row.amount,
                    due_date=row.due_date,
                    status=row.status,
                    created_at=row.created_at,
                    statement_id=statement_id,
                )
                return

    async def get_total_installments(self, card_movement_id: UUID) -> int:
        """`MAX(installment_number)` for this plan, derived over the FULL
        row set (billed and unbilled alike) — matches the real repository's
        `MAX()` semantics, not just the still-unbilled rows."""
        numbers = [
            row.installment_number
            for row in self.rows
            if row.card_movement_id == card_movement_id
        ]
        return max(numbers)


class FakeStatementRepository:
    """In-memory double for `IStatementRepository` — Credit Cards Phase 4.

    Finalization tracking mirrors the real repository: `status` moves
    `closed -> paid|overdue` once `finalize_due_date_outcome` runs, and
    `list_with_due_date(..., outcome_not_finalized=True)` filters on
    `status == closed` — the same trick that makes the double-finalize
    scenario provable against the fake alone.
    """

    def __init__(self):
        self.rows: dict[UUID, Statement] = {}

    async def exists_for_period(self, card_account_id: UUID, period_end) -> bool:
        return any(
            row.card_account_id == card_account_id and row.period_end == period_end
            for row in self.rows.values()
        )

    async def get_latest(self, card_account_id: UUID) -> Statement | None:
        candidates = [
            row for row in self.rows.values() if row.card_account_id == card_account_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: row.period_end)

    async def get_by_id(self, statement_id: UUID) -> Statement | None:
        return self.rows.get(statement_id)

    async def list_by_card_account_id(
        self, card_account_id: UUID, limit: int
    ) -> list[Statement]:
        candidates = [
            row for row in self.rows.values() if row.card_account_id == card_account_id
        ]
        candidates.sort(key=lambda row: row.period_end, reverse=True)
        return candidates[:limit]

    async def create(
        self,
        card_account_id: UUID,
        period_start,
        period_end,
        due_date,
        purchases_total: Decimal,
        interest_total: Decimal,
        total_due: Decimal,
        credit_balance: Decimal,
        late_fees_total: Decimal,
        minimum_payment: Decimal,
    ) -> Statement:
        now = _now()
        statement = Statement(
            id=uuid.uuid4(),
            card_account_id=card_account_id,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            purchases_total=purchases_total,
            interest_total=interest_total,
            total_due=total_due,
            paid_amount=Decimal(0),
            credit_balance=credit_balance,
            late_fees_total=late_fees_total,
            minimum_payment=minimum_payment,
            paid_in_full=False,
            paid_by_due_date=False,
            status=StatementStatus.CLOSED,
            created_at=now,
            updated_at=now,
        )
        self.rows[statement.id] = statement
        return statement

    async def list_with_due_date(
        self, due_date, outcome_not_finalized: bool
    ) -> list[Statement]:
        candidates = [row for row in self.rows.values() if row.due_date == due_date]
        if outcome_not_finalized:
            candidates = [
                row for row in candidates if row.status is StatementStatus.CLOSED
            ]
        return candidates

    async def finalize_due_date_outcome(
        self,
        statement_id: UUID,
        paid_amount: Decimal,
        paid_in_full: bool,
        paid_by_due_date: bool,
    ) -> None:
        current = self.rows.get(statement_id)
        if current is None:
            return
        new_status = StatementStatus.PAID if paid_in_full else StatementStatus.OVERDUE
        self.rows[statement_id] = Statement(
            id=current.id,
            card_account_id=current.card_account_id,
            period_start=current.period_start,
            period_end=current.period_end,
            due_date=current.due_date,
            purchases_total=current.purchases_total,
            interest_total=current.interest_total,
            total_due=current.total_due,
            paid_amount=paid_amount,
            credit_balance=current.credit_balance,
            late_fees_total=current.late_fees_total,
            minimum_payment=current.minimum_payment,
            paid_in_full=paid_in_full,
            paid_by_due_date=paid_by_due_date,
            status=new_status,
            created_at=current.created_at,
            updated_at=_now(),
        )
