"""`card-accounts` aggregator (split for 400-line guard).

`card_account_router` used to be a single 480-line module (Phase 1). To
respect the 400-line cap it was split into `card_account_read_router` and
`card_account_write_router` (§6). This module re-exports the combined router
so the mount point in `openbankapi/api/v1/main.py` is unchanged.

No endpoint logic lives here; each side owns its own prefix.
"""
from __future__ import annotations

from fastapi import APIRouter

from .card_account_read_router import router as read_router
from .card_account_write_router import router as write_router

router = APIRouter()
router.include_router(read_router)
router.include_router(write_router)
