"""Domain errors.

These carry no HTTP status. Translating a domain failure into a status code is
the controller's job (spec §7.2) — the domain layer must stay usable from a
consumer, a CLI or a test that has no notion of HTTP.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base for every error this domain raises."""


class NotFoundError(DomainError):
    """A resource addressed by the caller does not exist. -> 404"""

    def __init__(self, entity: str, identifier: object):
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class LocationNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("location", identifier)


class BranchNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("branch", identifier)


class CustomerNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("customer", identifier)


class AccountNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("account", identifier)


class ReferencedEntityNotFoundError(DomainError):
    """A foreign key in the request body points at nothing. -> 422

    Distinct from NotFoundError on purpose: the resource the caller *addressed*
    exists fine, it is a value inside their payload that is wrong, which is a
    validation failure rather than a bad URL (spec §11.4).
    """

    def __init__(self, field: str, identifier: object):
        self.field = field
        self.identifier = identifier
        super().__init__(f"referenced {field} does not exist: {identifier}")


class DuplicateError(DomainError):
    """A unique business key is already taken. -> 409"""

    def __init__(self, field: str, value: object):
        self.field = field
        self.value = value
        super().__init__(f"{field} already exists: {value}")


class DuplicateAccountNumberError(DuplicateError):
    def __init__(self, value: object):
        super().__init__("account_number", value)


class InvalidAccountNumberError(DomainError):
    """A 16-digit account number was expected. -> 400"""

    def __init__(self, value: object):
        self.value = value
        super().__init__(f"account_number must be 16 digits: {value!r}")


class AccountNotOperableError(DomainError):
    """The account exists but its status forbids the operation. -> 409"""

    def __init__(self, account_number: str, status: str):
        self.account_number = account_number
        self.status = status
        super().__init__(f"account {account_number} is {status}")


class CustomerAccountsNotEmptyError(DomainError):
    """A customer cannot be soft-deleted while an account isn't empty. -> 409

    "Empty" means every account is either not active (blocked/closed) or has a
    zero balance — not that the customer has no account rows at all. An
    account can carry funds and still be perfectly reachable after the
    customer is deactivated, so the caller must zero or close it first.
    """

    def __init__(self, customer_id: object):
        self.customer_id = customer_id
        super().__init__(
            f"customer {customer_id} still has an active account with a nonzero balance "
            "and cannot be deleted"
        )


class BranchHasActiveAccountsError(DomainError):
    """A branch cannot be soft-deleted while it still has an active account. -> 409

    Unlike a customer, a branch is reference data an account merely points at
    — there is no per-account balance rule here, only status: any account
    still `active` at this branch must be moved or closed first.
    """

    def __init__(self, branch_id: object):
        self.branch_id = branch_id
        super().__init__(f"The branch {branch_id} still has an active account and cannot be deleted")


class CustomerNotLinkedError(DomainError):
    """A valid Auth0 identity has no linked Customer. -> 404

    Distinct from `CustomerNotFoundError`: the token is fine, there is simply
    no customer record whose `auth0_sub` matches this identity yet (spec §1.2).
    """

    def __init__(self, sub: str):
        self.sub = sub
        super().__init__(f"no customer linked to this identity")


class AccountAccessForbiddenError(DomainError):
    """A resolved customer tried to reach an account they do not own. -> 403

    Distinct from `AccountNotFoundError`: the account exists, the caller is
    simply not entitled to see it (spec §3.4).
    """

    def __init__(self, account_number: str):
        self.account_number = account_number
        super().__init__(f"account {account_number} does not belong to this customer")


class CustomerAlreadyHasAccountError(DomainError):
    """A customer may only ever open one account through `POST /accounts/me`. -> 409

    Status-agnostic on purpose: owning even one closed, zero-balance account
    is still "already has an account" for the self-service flow — the generic
    multi-account `POST /accounts` path (staff-only) is unaffected.
    """

    def __init__(self, customer_id: object):
        self.customer_id = customer_id
        super().__init__(f"customer {customer_id} already owns an account")


class NoActiveBranchAvailableError(DomainError):
    """No ACTIVE branch exists to resolve as the default for a new account. -> 503

    Distinct from an unmapped bug: this is an operational/configuration state
    (no active branch has been set up yet), not a defect in the request.
    """

    def __init__(self):
        super().__init__("no active branch is available to open an account")


class InsufficientFundsError(DomainError):
    """Raised only where a balance decision is legitimately local.

    The ledger itself never raises this: Flink decides funds, and it reports a
    decline as an event, not an exception. Kept because the spec names it and
    because a future synchronous path would need it.
    """


class RateNotAvailableError(DomainError):
    """Frankfurter returned no usable rates. -> 502."""


class InsufficientPermissionsError(DomainError):
    """Caller lacks required RBAC permissions. -> 403

    Backend is security boundary; frontend hiding is UX only. Carries
    `required` and `had` so the handler can return them verbatim.
    """

    def __init__(self, required: list[str], had: list[str]):
        self.required = required
        self.had = had
        super().__init__(f"missing permissions {required!r}, had {had!r}")

class CardAccountNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("card_account", identifier)


class CardNotFoundError(NotFoundError):
    def __init__(self, identifier: object):
        super().__init__("card", identifier)


class DuplicateCardNumberError(DuplicateError):
    """A generated 16-digit card number collided. -> 409

    Mirrors `DuplicateAccountNumberError`: the repository retries internally
    on this one and only this one — see `postgres_card_repository.py`.
    """

    def __init__(self, value: object):
        super().__init__("card_number", value)


class InvalidCardNumberError(DomainError):
    """A 16-digit card number was expected. -> 400"""

    def __init__(self, value: object):
        self.value = value
        super().__init__(f"card_number must be 16 digits: {value!r}")


class InvalidCardStatusError(DomainError):
    """The requested status transition is not allowed from the current status. -> 409"""

    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(f"cannot transition from {current_status} to {target_status}")

