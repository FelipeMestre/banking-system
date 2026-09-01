"""Account creation orchestration (spec §3.5, §8.2).

Plain domain object: no FastAPI, no Depends, no import from `api` or `infra`
beyond the ports it needs. Per the architecture doc, the domain layer must
never depend on any other layer — its Dep wiring lives in
`config/dependencies.py`, not here.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from ...config import Settings
from ...infra.database.interfaces import IAccountRepository, IBranchRepository, ICustomerRepository
from ...infra.kafka.interfaces.event_publisher import IEventPublisher
from ..exceptions import CustomerAlreadyHasAccountError, NoActiveBranchAvailableError
from ..model import Account, Customer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AccountService:
    def __init__(
        self,
        settings: Settings,
        repository: IAccountRepository,
        publisher: IEventPublisher,
        branch_repository: Optional[IBranchRepository] = None,
        customer_repository: Optional[ICustomerRepository] = None,
    ):
        self._settings = settings
        self._repository = repository
        self._publisher = publisher
        self._branch_repository = branch_repository
        self._customer_repository = customer_repository

    async def open_first_account(self, customer: Customer) -> Account:
        """Self-service creation for a customer with zero existing accounts.

        Lock-then-check-then-insert, all inside the request's single shared
        transaction (spec: concurrent duplicate requests must not both
        succeed). The lock is acquired first so the guard check below can
        never race with another request for the same customer.
        """
        assert self._branch_repository is not None, "AccountService needs a branch_repository for open_first_account"
        await self._repository.lock_customer_for_account_creation(customer.id)
        if await self._repository.has_any_account_for_customer(customer.id):
            raise CustomerAlreadyHasAccountError(customer.id)
        branch = await self._branch_repository.get_oldest_active()
        if branch is None:
            raise NoActiveBranchAvailableError()
        return await self.open_account(currency="USD", customer_id=customer.id, branch_id=branch.id)

    async def open_first_account_for_identity(
        self,
        sub: str,
        *,
        identification_number: str,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        gender: Optional[str] = None,
    ) -> Account:
        """Auto-link a never-before-seen Auth0 identity and open its first account.

        The caller (the router) has already validated the KYC fields against
        the strict `FirstAccountKycDTO` — this method stays a plain domain
        object with no knowledge of Pydantic or the API layer, per this
        codebase's layering rule (the domain never imports from `api`).

        Lock-then-recheck-then-insert, mirroring `open_first_account`'s own
        ordering: the identity-keyed advisory lock is acquired before the
        post-lock re-check, so two concurrent requests for the same
        never-before-seen `sub` cannot both create a `Customer`. The
        `UNIQUE(auth0_sub)` constraint (translated to `DuplicateError` -> 409
        by `errors.py`) remains the final line of defense if the lock is ever
        bypassed or a genuine race lands between the re-check and the insert.
        """
        assert self._customer_repository is not None, (
            "AccountService needs a customer_repository for open_first_account_for_identity"
        )
        customer = await self._customer_repository.get_by_auth0_sub(sub)
        if customer is not None:
            return await self.open_first_account(customer)

        await self._repository.lock_identity_for_account_creation(sub)
        customer = await self._customer_repository.get_by_auth0_sub(sub)
        if customer is None:
            customer = await self._customer_repository.create(
                identification_number=identification_number,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                gender=gender,
                auth0_sub=sub,
            )
        return await self.open_first_account(customer)

    async def open_account(
        self, *, currency: str, customer_id: UUID, branch_id: UUID
    ) -> Account:
        """Create the account row.

        No opening balance is written here, ever. A new account starts at 0 on
        both sides with no synchronisation needed: Postgres defaults `balance` to
        0, and Flink lazily initialises an account's keyed state to 0 the first
        time it sees any event for that key. They agree at t=0 for free.
        """
        return await self._repository.create(
            currency=currency, customer_id=customer_id, branch_id=branch_id
        )

    def credit_opening_balance(self, account_number: str, amount: int) -> Dict[str, Any]:
        """Give an account a non-zero opening balance the event-sourced way.

        Never a direct UPDATE on `accounts.balance` (spec §3.5). The credit takes
        the same path as every other credit in the system: an `incoming_payment`
        on `account-events`, which Flink applies and then announces back through
        `account-balances`. The read model updates as a consequence, not as a
        separate write.
        """
        event = {
            "type": "incoming_payment",
            "request_id": f"seed-{uuid.uuid4()}",
            "account_id": account_number,
            "amount": amount,
            "leg": "credit:seed",
            "ts": _now(),
        }
        self._publisher.publish(
            topic=self._settings.account_events_topic,
            key=account_number,
            value=event,
        )
        return event