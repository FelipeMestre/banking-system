"""Admin manual-trigger DTOs for the Phase 4 monthly-batch jobs.

Both response shapes mirror what `batch/run_once.py`'s real functions
actually produce — a count plus the identifiers affected — so an admin
testing the batch worker on demand (instead of waiting for the hourly cron
or faking server time) gets a concrete, auditable result rather than a bare
"ok"."""
from __future__ import annotations

from typing import List
from uuid import UUID

from pydantic import BaseModel


class MonthlyCloseRunResultDTO(BaseModel):
    closed_count: int
    statement_ids: List[UUID]
    card_account_ids: List[UUID]


class DueDateCheckRunResultDTO(BaseModel):
    finalized_count: int
    late_fees_applied_count: int
