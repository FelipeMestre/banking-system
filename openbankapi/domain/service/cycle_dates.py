"""Shared statement-cycle date math for the credit-card domain.

Extracted verbatim from `batch/run_once.py`'s `next_close_date_after`/
`_close_day_in_month` so `current_cycle_projection_service.py` can compute a
projected period end without depending on a batch/script module (a domain
module must not import from `batch/`, per AGENTS.MD layering). This is an
import-only extraction: no logic changed from the original functions.
"""
from __future__ import annotations

import calendar
from datetime import date


def next_close_date_after(after: date, close_day: int) -> date:
    """The next close date on/after `after`, using `close_day` as the target
    day-of-month (clamped to the last day of a short month, e.g. Feb).
    """
    candidate = _close_day_in_month(after.year, after.month, close_day)
    if candidate >= after:
        return candidate
    year, month = after.year, after.month + 1
    if month > 12:
        month = 1
        year += 1
    return _close_day_in_month(year, month, close_day)


def previous_close_date_before(before: date, close_day: int) -> date:
    """The latest close date strictly before `before`, using `close_day` as
    the target day-of-month. Mirror image of `next_close_date_after`, used
    to derive historical (already-closed) periods aligned to the same
    calendar schedule the batch worker enforces going forward.
    """
    candidate = _close_day_in_month(before.year, before.month, close_day)
    if candidate < before:
        return candidate
    year, month = before.year, before.month - 1
    if month < 1:
        month = 12
        year -= 1
    return _close_day_in_month(year, month, close_day)


def _close_day_in_month(year: int, month: int, close_day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(close_day, last_day))
