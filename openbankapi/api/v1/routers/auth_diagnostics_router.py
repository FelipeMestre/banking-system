"""Auth0 integration smoke test — public/private/scoped endpoints (spec: n/a).

Deliberately separate from the business routers: this exists to prove the
Auth0 wiring works end to end (no token / any token / a scoped token),
not to be a real product endpoint. Nothing here should stay once the actual
business routes decide, one by one, whether they need `CurrentUserDep` or
`require_scope(...)`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from openbankapi.config.dependencies import CurrentUserDep, require_scope

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/public")
async def public():
    return {"message": "Hello from a public endpoint! You don't need to be authenticated to see this."}


@router.get("/private")
async def private(claims: CurrentUserDep):
    return {
        "message": "Hello from a private endpoint! You need to be authenticated to see this.",
        "user_id": claims.get("sub"),
    }


@router.get("/private-scoped")
async def private_scoped(claims: Annotated[dict, Depends(require_scope("read:messages"))]):
    return {
        "message": (
            "Hello from a private endpoint! You need to be authenticated and have a "
            "scope of read:messages to see this."
        ),
        "user_id": claims.get("sub"),
    }
