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
from ..domain.exceptions import CustomerNotLinkedError
from ..domain.model import Customer
from ..domain.service.account_service import AccountService
from ..domain.service.branch_service import BranchService
from ..domain.service.customer_service import CustomerService
from ..domain.service.transaction_service import TransactionService
from ..domain.service.transfer_service import TransferService
from ..infra.cache.interfaces.cache_service import ICacheService
from ..infra.database.interfaces import (
    IAccountRepository,
    IBranchRepository,
    ICustomerRepository,
    ILocationRepository,
    ITransactionRepository,
)
from ..infra.database.repositories import (
    PostgresAccountRepository,
    PostgresBranchRepository,
    PostgresCustomerRepository,
    PostgresLocationRepository,
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


# --- repositories: request-scoped, built fresh on the shared session --------


def get_location_repository(session: DbSession) -> ILocationRepository:
    return PostgresLocationRepository(session)


LocationRepositoryDep = Annotated[ILocationRepository, Depends(get_location_repository)]


def get_branch_repository(session: DbSession) -> IBranchRepository:
    return PostgresBranchRepository(session)


BranchRepositoryDep = Annotated[IBranchRepository, Depends(get_branch_repository)]


def get_customer_repository(session: DbSession) -> ICustomerRepository:
    return PostgresCustomerRepository(session)


CustomerRepositoryDep = Annotated[ICustomerRepository, Depends(get_customer_repository)]


def get_account_repository(session: DbSession) -> IAccountRepository:
    return PostgresAccountRepository(session)


AccountRepositoryDep = Annotated[IAccountRepository, Depends(get_account_repository)]


def get_transaction_repository(session: DbSession) -> ITransactionRepository:
    return PostgresTransactionRepository(session)


TransactionRepositoryDep = Annotated[ITransactionRepository, Depends(get_transaction_repository)]


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
    branch_repository: BranchRepositoryDep,
    customer_repository: CustomerRepositoryDep,
) -> AccountService:
    return AccountService(settings, repository, publisher, branch_repository, customer_repository)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


def get_transfer_service(settings: SettingsDep, publisher: PublisherDep) -> TransferService:
    return TransferService(settings, publisher)


TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]


def get_customer_service(
    customer_repository: CustomerRepositoryDep,
    account_repository: AccountRepositoryDep,
) -> CustomerService:
    return CustomerService(customer_repository, account_repository)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_branch_service(
    branch_repository: BranchRepositoryDep,
    account_repository: AccountRepositoryDep,
) -> BranchService:
    return BranchService(branch_repository, account_repository)


BranchServiceDep = Annotated[BranchService, Depends(get_branch_service)]


def get_transaction_service(repository: TransactionRepositoryDep) -> TransactionService:
    return TransactionService(repository)


TransactionServiceDep = Annotated[TransactionService, Depends(get_transaction_service)]
