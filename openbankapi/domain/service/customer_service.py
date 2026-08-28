"""Customer soft-delete orchestration (spec §8.2).

Plain domain object: no FastAPI, no Depends, no import from `api` beyond the
ports it needs. Per the architecture doc, the domain layer must never depend
on any other layer — its Dep wiring lives in `config/dependencies.py`, not
here.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ...infra.database.interfaces import IAccountRepository, ICustomerRepository
from ..exceptions import CustomerAccountsNotEmptyError
from ..model import Customer


class CustomerService:
    def __init__(self, customer_repository: ICustomerRepository, account_repository: IAccountRepository):
        self._customers = customer_repository
        self._accounts = account_repository

    async def deactivate(self, customer_id: UUID) -> Optional[Customer]:
        """Soft-delete a customer, refusing while an account isn't empty.

        Orchestrates two repositories, which is exactly the case the
        architecture reserves for a domain service rather than a controller
        calling one repository directly. "Empty" means every account is
        either not active or sits at a zero balance — a closed account, or an
        active one with nothing in it, does not block this.
        """
        if await self._accounts.has_nonempty_account_for_customer(customer_id):
            raise CustomerAccountsNotEmptyError(customer_id)
        return await self._customers.deactivate(customer_id)
