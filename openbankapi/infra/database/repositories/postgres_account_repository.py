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

from sqlalchemy import select, update as sql_update
from sqlalchemy.exc import IntegrityError

from ....domain.exceptions import DuplicateAccountNumberError
from ....domain.model import ACCOUNT_NUMBER_LENGTH, Account, AccountStatus
from ..errors import translate
from ..interfaces.common import Page
from ..models import AccountORM
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
                async with self._sessionmaker.begin() as session:
                    row = AccountORM(**values)
                    session.add(row)
                    await session.flush()
                    await session.refresh(row)
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

    async def list(self, *, limit: int, offset: int) -> Page:
        rows, total = await self._fetch_page(AccountORM, limit=limit, offset=offset)
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


class PostgresAccountBalanceProjection(PostgresRepository):
    """The only writer of `accounts.balance` (spec §3.6).

    Kept as a separate class so the capability travels separately: `main.py`
    hands one of these to the `account-balances` consumer and to nothing else.
    """

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
