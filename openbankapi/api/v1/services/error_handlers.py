"""Domain error -> HTTP status. This translation lives here and nowhere else.

The domain raises meaning; the transport decides what that means over HTTP
(spec §7.2). Keeping the mapping in one table is what stops a status code from
being invented independently in five controllers.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ....domain.exceptions import (
    AccountAccessForbiddenError,
    AccountNotOperableError,
    BranchHasActiveAccountsError,
    CustomerAccountsNotEmptyError,
    CustomerAlreadyHasAccountError,
    CustomerNotLinkedError,
    DomainError,
    DuplicateError,
    InsufficientFundsError,
    InsufficientPermissionsError,
    InvalidAccountNumberError,
    InvalidCardNumberError,
    InvalidCardStatusError,
    NoActiveBranchAvailableError,
    NotFoundError,
    RateNotAvailableError,
    ReferencedEntityNotFoundError,
)

LOG = logging.getLogger("openbankapi.errors")

_STATUS = [
    (RateNotAvailableError, 502),
    (NotFoundError, 404),
    (CustomerNotLinkedError, 404),
    (ReferencedEntityNotFoundError, 422),
    (DuplicateError, 409),
    (AccountNotOperableError, 409),
    (InvalidAccountNumberError, 400),
    (InsufficientFundsError, 409),
    (CustomerAccountsNotEmptyError, 409),
    (BranchHasActiveAccountsError, 409),
    (AccountAccessForbiddenError, 403),
    (CustomerAlreadyHasAccountError, 409),
    (NoActiveBranchAvailableError, 503),
    (InsufficientPermissionsError, 403),
    (InvalidCardStatusError, 409),
    (InvalidCardNumberError, 400),
]


def status_for(error: DomainError) -> int:
    for kind, status in _STATUS:
        if isinstance(error, kind):
            return status
    return 500


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def install(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, error: DomainError):
        status = status_for(error)
        if status >= 500:
            LOG.exception("unmapped domain error", exc_info=error)
        # InsufficientPermissionsError needs structured details for 403 {required,had}
        if isinstance(error, InsufficientPermissionsError):
            return JSONResponse(
                status_code=status,
                content=error_body(
                    type(error).__name__,
                    str(error),
                    {"required": error.required, "had": error.had},
                ),
            )
        return JSONResponse(
            status_code=status,
            content=error_body(type(error).__name__, str(error)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, error: RequestValidationError):
        # Strip `input`: pydantic echoes the rejected value back, which would
        # put a date_of_birth in an HTTP response body (spec §3.4).
        details = [
            {k: v for k, v in item.items() if k != "input"} for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("ValidationError", "request validation failed", details),
        )
