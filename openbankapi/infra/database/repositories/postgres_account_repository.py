"""Postgres implementation of the two `accounts` ports.

`PostgresAccountRepository` implements `IAccountRepository` and has no code path
that writes `balance`. `PostgresAccountBalanceProjection` implements
`IAccountBalanceProjection` and is the only thing in the system that does; it is
constructed once, in `main.py`, and handed only to the balance consumer.
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
from typing import Optional
from uuid import UUID

from sqlalchemy import exists, select, text, update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.exceptions import DuplicateAccountNumberError
from ....domain.model import ACCOUNT_NUMBER_LENGTH, Account, AccountStatus
from ..errors import translate
from ..interfaces.common import Page
from ..schemas.models import AccountORM
from ._base import PostgresRepository, page_of

LOG = logging.getLogger("openbankapi.accounts")

# How many times to re-roll a colliding account number before giving up. With
# 10^16 possibilities a single collision is already improbable; three in a row
# means something is wrong with the generator, not with luck.
_GENERATION_ATTEMPTS = 5


def generate_account_number() -> str:
    """16 random digits, leading zeros preserved.

    `secrets` rather than `random`: this value is a publicly quoted account
    identifier, and a predictable sequence would let anyone enumerate accounts.
    """
    return "".join(secrets.choice("0123456789") for _ in range(ACCOUNT_NUMBER_LENGTH))


def _to_domain(row: AccountORM) -> Account:
    return Account(
        id=row.id,
        account_number=row.account_number,
        currency=row.currency,
        customer_id=row.customer_id,
        branch_id=row.branch_id,
        balance=row.balance,
        status=AccountStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresAccountRepository(PostgresRepository):
    # Belt and braces alongside the DTO: even an internal caller cannot name
    # balance here, because _update is only ever fed these keys.
    _UPDATABLE = frozenset({"currency", "branch_id", "status"})

    async def create(self, *, currency: str, customer_id: UUID, branch_id: UUID) -> Account:
        """Insert with a server-generated number, retrying on collision.

        The retry is what keeps spec §11.1 true: a UNIQUE violation on the
        generated number is an internal detail and must never reach the client
        as a 500. A violation on customer_id/branch_id is a different thing
        entirely — that is the caller's bad input, so it is translated and
        raised immediately rather than retried.

        Each attempt runs inside its own SAVEPOINT (`begin_nested`), not a new
        transaction: this session is shared for the whole request (see
        `_base.py`), so a colliding attempt must only undo that one insert, not
        abort whatever else the request has already done, or block the next
        retry — a plain `flush()` failure would otherwise leave the entire
        session's transaction unusable for anything that follows.
        """
        last: Optional[DuplicateAccountNumberError] = None
        for attempt in range(_GENERATION_ATTEMPTS):
            account_number = generate_account_number()
            values = {
                "account_number": account_number,
                "currency": currency,
                "customer_id": customer_id,
                "branch_id": branch_id,
            }
            try:
                async with self._session.begin_nested():
                    row = AccountORM(**values)
                    self._session.add(row)
                    await self._session.flush()
                await self._session.refresh(row)
                return _to_domain(row)
            except IntegrityError as error:
                translated = translate(error, values=values)
                if not isinstance(translated, DuplicateAccountNumberError):
                    raise translated from error
                last = translated
                LOG.warning("account_number collision on attempt %d; retrying", attempt + 1)
        raise last if last else RuntimeError("account creation failed without a cause")

    async def get_by_account_number(self, account_number: str) -> Optional[Account]:
        row = await self._fetch_one(AccountORM, AccountORM.account_number == account_number)
        return _to_domain(row) if row else None

    async def get_by_id(self, account_id: UUID) -> Optional[Account]:
        row = await self._fetch_one(AccountORM, AccountORM.id == account_id)
        return _to_domain(row) if row else None

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(AccountORM, limit=limit, offset=offset)
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def list_by_customer(self, customer_id: UUID, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(
            AccountORM, AccountORM.customer_id == customer_id, limit=limit, offset=offset
        )
        return page_of([_to_domain(r) for r in rows], total, limit, offset)

    async def update(
        self,
        account_number: str,
        *,
        currency: Optional[str] = None,
        branch_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Optional[Account]:
        candidate = {"currency": currency, "branch_id": branch_id, "status": status}
        assert set(candidate) <= self._UPDATABLE, "balance is not updatable here"
        row = await self._update(
            AccountORM, AccountORM.account_number == account_number, candidate
        )
        return _to_domain(row) if row else None

    async def close(self, account_number: str) -> Optional[Account]:
        row = await self._update(
            AccountORM,
            AccountORM.account_number == account_number,
            {"status": AccountStatus.CLOSED.value},
        )
        return _to_domain(row) if row else None

    async def has_nonempty_account_for_customer(self, customer_id: UUID) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        AccountORM.customer_id == customer_id,
                        AccountORM.status == AccountStatus.ACTIVE.value,
                        AccountORM.balance != 0,
                    )
                )
            )
        )

    async def has_active_account_for_branch(self, branch_id: UUID) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        AccountORM.branch_id == branch_id,
                        AccountORM.status == AccountStatus.ACTIVE.value,
                    )
                )
            )
        )

    async def has_any_account_for_customer(self, customer_id: UUID) -> bool:
        # Status-agnostic on purpose (spec: "any account, any status") — see
        # the port docstring for why this differs from the nonempty check.
        return bool(
            await self._session.scalar(
                select(exists().where(AccountORM.customer_id == customer_id))
            )
        )

    async def lock_customer_for_account_creation(self, customer_id: UUID) -> None:
        # Transaction-scoped advisory lock: released automatically at commit
        # or rollback, never held past this request's single shared session
        # (see _base.py's Unit-of-Work docstring). `hashtext` folds the UUID
        # into the bigint key `pg_advisory_xact_lock` expects.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:customer_id))"),
            {"customer_id": str(customer_id)},
        )

    async def lock_identity_for_account_creation(self, auth0_sub: str) -> None:
        # Mirrors lock_customer_for_account_creation above, re-keyed on the
        # Auth0 `sub` string for the never-linked-identity path (amendment),
        # where no customer_id exists yet.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:sub))"),
            {"sub": auth0_sub},
        )


class PostgresAccountBalanceProjection:
    """The only writer of `accounts.balance` (spec §3.6).

    Deliberately NOT a `PostgresRepository`: that base class now expects an
    already-open, request-scoped `AsyncSession` handed out by
    `infra/database/session.get_db_session` (see `_base.py`) — but this class
    is driven by the `account-balances` Kafka consumer thread, not an HTTP
    request, so there is no request to scope a session to. It keeps its own
    `sessionmaker` and opens one session per call instead. Constructed once in
    `main.py` and handed only to that consumer — nothing that serves an HTTP
    request may ever hold one.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def apply_balance(self, account_number: str, balance: int) -> bool:
        async with self._sessionmaker.begin() as session:
            result = await session.execute(
                sql_update(AccountORM)
                .where(AccountORM.account_number == account_number)
                .values(balance=balance, updated_at=dt.datetime.now(dt.timezone.utc))
            )
            # rowcount 0 means the ledger knows an account that reference data
            # does not. That is legitimate, not an error — see the port docs.
            return bool(result.rowcount)

    async def read_balance(self, account_number: str) -> Optional[int]:
        """Only used by tests and diagnostics."""
        async with self._sessionmaker() as session:
            return await session.scalar(
                select(AccountORM.balance).where(AccountORM.account_number == account_number)
            )