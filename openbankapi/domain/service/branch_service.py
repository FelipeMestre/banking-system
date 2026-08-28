"""Branch soft-delete orchestration (spec §8.2).

Plain domain object: no FastAPI, no Depends, no import from `api` beyond the
ports it needs. Per the architecture doc, the domain layer must never depend
on any other layer — its Dep wiring lives in `config/dependencies.py`, not
here.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from ...infra.database.interfaces import IAccountRepository, IBranchRepository
from ..exceptions import BranchHasActiveAccountsError
from ..model import Branch


class BranchService:
    def __init__(self, branch_repository: IBranchRepository, account_repository: IAccountRepository):
        self._branches = branch_repository
        self._accounts = account_repository

    async def deactivate(self, branch_id: UUID) -> Optional[Branch]:
        """Soft-delete a branch, refusing while it still has an active account.

        Orchestrates two repositories, which is exactly the case the
        architecture reserves for a domain service rather than a controller
        calling one repository directly.
        """
        if await self._accounts.has_active_account_for_branch(branch_id):
            raise BranchHasActiveAccountsError(branch_id)
        return await self._branches.deactivate(branch_id)
