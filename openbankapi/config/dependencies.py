"""Dependency-injection wiring for the whole app.

This is not a layer's concern — it's FastAPI's own `Depends` mechanism being
configured, so it lives beside `config.py` rather than inside `api/`,
`domain/`, or `infra/`. Putting it in `infra/` would be wrong too: infra is a
facade for external dependencies (Postgres, Redis, Kafka), not for the web
framework itself.

Three kinds of things are wired here:

- Process-wide singletons (settings, cache, the Kafka publisher, the status
  registry) are built ONCE in the composition root (`main.py`) and stashed on
  `app.state`. Every provider below just reads one back — it never constructs
  one.
- Repositories are request-scoped: each is built fresh on the shared
  `DbSession` (`infra/database/session.DbSession`), so a whole request shares
  one session, one transaction — the Unit of Work `session.py` documents.
- The two domain services (`AccountService`, `TransferService`) are plain
  classes with no FastAPI import of their own — composing them from their
  dependencies is exactly the kind of framework wiring that belongs here.

Every "read app.state" dependency is typed `HTTPConnection`, not `Request`:
`HTTPConnection` is the base class both `Request` and `WebSocket` inherit
`.app` from, so the exact same function works unmodified from the transfer
endpoints' WebSocket route (see `fastapi.tiangolo.com/advanced/websockets` —
"dependencies compatible with both HTTP and WebSockets can define a parameter
taking an HTTPConnection").
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request
from fastapi_plugin.fast_api_client import Auth0FastAPI
from starlette.requests import HTTPConnection

from .config import Settings
from ..domain.exceptions import CustomerNotLinkedError, InsufficientPermissionsError, InvalidAdminIdentityError
from ..domain.model import Customer
from ..domain.service.account_service import AccountService
from ..domain.service.card_account_service import CardAccountService
from ..domain.service.customer_service import CustomerService
from ..domain.service.statement_service import StatementService
from ..domain.service.transaction_service import TransactionService
from ..domain.service.transfer_service import TransferService
from ..infra.cache.interfaces.cache_service import ICacheService
from ..infra.database.interfaces import (
    IAccountRepository,
    IAppliedRateRepository,
    ICardAccountAdminActionRepository,
    ICardAccountRepository,
    ICardMovementRepository,
    ICardRepository,
    ICustomerRepository,
    IInstallmentRepository,
    IStatementRepository,
    ITransactionRepository,
)
from ..infra.database.repositories import (
    PostgresAccountRepository,
    PostgresAppliedRateRepository,
    PostgresCardAccountAdminActionRepository,
    PostgresCardAccountRepository,
    PostgresCardMovementRepository,
    PostgresCardRepository,
    PostgresCustomerRepository,
    PostgresInstallmentRepository,
    PostgresStatementRepository,
    PostgresTransactionRepository,
)
from ..infra.database.config.session import DbSession
from ..infra.kafka.interfaces.event_publisher import IEventPublisher
from ..infra.kafka.status_registry import StatusRegistry

# --- process-wide singletons, read back off app.state -----------------------


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_cache(conn: HTTPConnection) -> ICacheService:
    return conn.app.state.cache


CacheDep = Annotated[ICacheService, Depends(get_cache)]


def get_publisher(conn: HTTPConnection) -> IEventPublisher:
    return conn.app.state.publisher


PublisherDep = Annotated[IEventPublisher, Depends(get_publisher)]


def get_status_registry(conn: HTTPConnection) -> StatusRegistry:
    return conn.app.state.status_registry


StatusRegistryDep = Annotated[StatusRegistry, Depends(get_status_registry)]


def get_purchase_status_registry(conn: HTTPConnection) -> StatusRegistry:
    # A separate instance from `status_registry` (transfers): `request_id`
    # is only unique within its own domain's Kafka topic, and a card
    # purchase and a transfer could coincidentally share one.
    return conn.app.state.purchase_status_registry


PurchaseStatusRegistryDep = Annotated[StatusRegistry, Depends(get_purchase_status_registry)]


def get_card_payment_status_registry(conn: HTTPConnection) -> StatusRegistry:
    # A THIRD separate instance (never `status_registry` or
    # `purchase_status_registry`): `request_id` is only unique within its own
    # domain's Kafka topic, and a card payment could coincidentally share one
    # with a transfer or a purchase.
    return conn.app.state.card_payment_status_registry


CardPaymentStatusRegistryDep = Annotated[StatusRegistry, Depends(get_card_payment_status_registry)]


def get_deposit_status_registry(conn: HTTPConnection) -> StatusRegistry:
    # A FOURTH separate instance: `request_id` is only unique within its own
    # domain's Kafka topic.
    return conn.app.state.deposit_status_registry


DepositStatusRegistryDep = Annotated[StatusRegistry, Depends(get_deposit_status_registry)]


def get_withdrawal_status_registry(conn: HTTPConnection) -> StatusRegistry:
    # A FIFTH separate instance: `request_id` is only unique within its own
    # domain's Kafka topic.
    return conn.app.state.withdrawal_status_registry


WithdrawalStatusRegistryDep = Annotated[StatusRegistry, Depends(get_withdrawal_status_registry)]


def get_foreign_exchange_cache_service(conn: HTTPConnection):
    return conn.app.state.foreign_exchange_cache_service


ForeignExchangeCacheServiceDep = Annotated[object, Depends(get_foreign_exchange_cache_service)]


def get_auth0(conn: HTTPConnection) -> Optional[Auth0FastAPI]:
    return conn.app.state.auth0


Auth0Dep = Annotated[Optional[Auth0FastAPI], Depends(get_auth0)]


def _require_auth0(auth0: Optional[Auth0FastAPI]) -> Auth0FastAPI:
    if auth0 is None:
        raise HTTPException(
            status_code=503,
            detail="Auth0 is not configured — set AUTH0_DOMAIN and AUTH0_AUDIENCE.",
        )
    return auth0


async def get_current_user(request: Request, auth0: Auth0Dep) -> dict:
    """Requires a valid Access Token; returns its decoded claims."""
    return await _require_auth0(auth0).require_auth()(request)


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


def require_scope(scope: str):
    """Like `CurrentUserDep`, but also requires `scope` in the token's `scope` claim."""

    async def _dependency(request: Request, auth0: Auth0Dep) -> dict:
        return await _require_auth0(auth0).require_auth(scopes=scope)(request)

    return _dependency


def _effective_permissions(claims: dict) -> list[str]:
    """permissions[] primary, scope fallback (spec admin-authorization).

    - If `permissions` is a non-empty list, use it verbatim.
    - Otherwise, fall back to space-split `scope` string.
    - Else empty.
    """
    perms = claims.get("permissions")
    if isinstance(perms, list) and perms:
        return [str(p) for p in perms]
    scope = claims.get("scope")
    if isinstance(scope, str) and scope.strip():
        return scope.split()
    return []


def require_permissions(*required: str):
    """Require all `required` permissions (401 handled by CurrentUserDep, 403 here)."""

    async def _dependency(claims: CurrentUserDep) -> dict:
        had = _effective_permissions(claims)
        if not all(r in had for r in required):
            raise InsufficientPermissionsError(list(required), had)
        return claims

    return _dependency


# `admin:batch` is an RBAC permission (checked via `permissions[]`/`scope`
# fallback, same as `read:admin`/`write:admin`), not an OAuth2 `scope` —
# `require_permissions` is the correct check here, not `require_scope`.
require_admin_batch_permission = require_permissions("admin:batch")

RequireAdminBatchPermissionDep = Annotated[dict, Depends(require_admin_batch_permission)]


# `write:admin` gates every card-account/card admin mutation this change adds
# (issue, update_limit, update_status, renew, card_status — spec's five sync
# points). `InsufficientPermissionsError` (403) already covers "authenticated
# but lacking the permission"; `_require_admin_identity` below covers the
# narrower "authenticated, has the permission, but the token carries no
# usable `sub`" case, which is a 401 (design D3).
require_write_admin_permission = require_permissions("write:admin")

WriteAdminDep = Annotated[dict, Depends(require_write_admin_permission)]


def _require_admin_identity(claims: WriteAdminDep) -> str:
    """The admin's `sub` claim, or `InvalidAdminIdentityError` (401) if it is
    missing/empty — called before any of the five audited mutations write
    anything (design D3)."""
    sub = claims.get("sub")
    if not sub:
        raise InvalidAdminIdentityError()
    return sub


AdminIdentityDep = Annotated[str, Depends(_require_admin_identity)]


# --- repositories: request-scoped, built fresh on the shared session --------


def get_customer_repository(session: DbSession) -> ICustomerRepository:
    return PostgresCustomerRepository(session)


CustomerRepositoryDep = Annotated[ICustomerRepository, Depends(get_customer_repository)]


def get_account_repository(session: DbSession) -> IAccountRepository:
    return PostgresAccountRepository(session)


AccountRepositoryDep = Annotated[IAccountRepository, Depends(get_account_repository)]


def get_applied_rate_repository(session: DbSession) -> IAppliedRateRepository:
    return PostgresAppliedRateRepository(session)


AppliedRateRepositoryDep = Annotated[IAppliedRateRepository, Depends(get_applied_rate_repository)]

def get_transaction_repository(session: DbSession) -> ITransactionRepository:
    return PostgresTransactionRepository(session)


TransactionRepositoryDep = Annotated[ITransactionRepository, Depends(get_transaction_repository)]


def get_card_account_repository(session: DbSession) -> ICardAccountRepository:
    return PostgresCardAccountRepository(session)


CardAccountRepositoryDep = Annotated[ICardAccountRepository, Depends(get_card_account_repository)]


def get_card_repository(session: DbSession) -> ICardRepository:
    return PostgresCardRepository(session)


CardRepositoryDep = Annotated[ICardRepository, Depends(get_card_repository)]


def get_card_movement_repository(session: DbSession) -> ICardMovementRepository:
    return PostgresCardMovementRepository(session)


CardMovementRepositoryDep = Annotated[
    ICardMovementRepository, Depends(get_card_movement_repository)
]


def get_installment_repository(session: DbSession) -> IInstallmentRepository:
    return PostgresInstallmentRepository(session)


InstallmentRepositoryDep = Annotated[IInstallmentRepository, Depends(get_installment_repository)]


def get_statement_repository(session: DbSession) -> IStatementRepository:
    return PostgresStatementRepository(session)


StatementRepositoryDep = Annotated[IStatementRepository, Depends(get_statement_repository)]


def get_admin_action_repository(session: DbSession) -> ICardAccountAdminActionRepository:
    return PostgresCardAccountAdminActionRepository(session)


AdminActionRepositoryDep = Annotated[
    ICardAccountAdminActionRepository, Depends(get_admin_action_repository)
]


async def get_current_customer(
    claims: CurrentUserDep, customer_repository: CustomerRepositoryDep
) -> Customer:
    """The Customer linked to the caller's Auth0 identity (spec §1.2).

    `CurrentUserDep` already turned an invalid/missing token into a 401 before
    this ever runs; the only decision left here is 404 vs resolved.
    """
    customer = await customer_repository.get_by_auth0_sub(claims.get("sub", ""))
    if customer is None:
        raise CustomerNotLinkedError(claims.get("sub", ""))
    return customer


CurrentCustomerDep = Annotated[Customer, Depends(get_current_customer)]


# --- domain services: plain classes, composed here where FastAPI is allowed -


def get_account_service(
    settings: SettingsDep,
    repository: AccountRepositoryDep,
    publisher: PublisherDep,
    customer_repository: CustomerRepositoryDep,
) -> AccountService:
    return AccountService(settings, repository, publisher, customer_repository)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


def get_transfer_service(
    settings: SettingsDep,
    publisher: PublisherDep,
    account_repository: AccountRepositoryDep,
    foreign_exchange_cache_service: ForeignExchangeCacheServiceDep,
) -> TransferService:
    return TransferService(settings, publisher, account_repository, foreign_exchange_cache_service)


TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]


def get_customer_service(
    customer_repository: CustomerRepositoryDep,
    account_repository: AccountRepositoryDep,
) -> CustomerService:
    return CustomerService(customer_repository, account_repository)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_transaction_service(repository: TransactionRepositoryDep) -> TransactionService:
    return TransactionService(repository)


TransactionServiceDep = Annotated[TransactionService, Depends(get_transaction_service)]


def get_card_account_service(
    card_account_repository: CardAccountRepositoryDep,
    card_repository: CardRepositoryDep,
) -> CardAccountService:
    return CardAccountService(card_account_repository, card_repository)


CardAccountServiceDep = Annotated[CardAccountService, Depends(get_card_account_service)]


def get_statement_service(
    settings: SettingsDep,
    statement_repository: StatementRepositoryDep,
    card_movement_repository: CardMovementRepositoryDep,
    installment_repository: InstallmentRepositoryDep,
    card_repository: CardRepositoryDep,
) -> StatementService:
    return StatementService(
        statement_repository, card_movement_repository, installment_repository, card_repository,
        credit_card_apr=settings.credit_card_apr,
        late_fee_amount=settings.late_fee_amount,
        minimum_payment_rate=settings.minimum_payment_rate,
        due_date_offset_days=settings.due_date_offset_days,
    )


StatementServiceDep = Annotated[StatementService, Depends(get_statement_service)]
