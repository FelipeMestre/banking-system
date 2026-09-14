"""RED/GREEN for the admin manual-trigger endpoints
(`POST /admin/batch/monthly-close`, `POST /admin/batch/due-date-check`).

These endpoints call the exact same real functions the hourly
`batch-worker` cron calls (`check_and_close_if_due`,
`StatementService.run_due_date_check`) — mirrors `test_batch_run_once.py`'s
scenarios, but exercised through the HTTP router instead of calling the
functions directly, proving the `Depends`-wired repositories actually reach
the real batch logic.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from openbankapi.config.dependencies import get_current_user, get_statement_repository
from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeStatementRepository

CLOSE_DAY = 20


def _admin_claims() -> dict:
    # `admin:batch` is an RBAC permission, not an OAuth2 scope — real callers
    # carry it in `permissions[]`; `require_permissions` also falls back to a
    # space-split `scope` string, exercised separately below.
    return {"sub": "auth0|admin-test", "permissions": ["admin:batch"]}


def _non_admin_claims() -> dict:
    return {"sub": "auth0|not-admin", "permissions": []}


def _harness():
    h = build()
    h.statements = FakeStatementRepository()
    h.client.app.dependency_overrides[get_statement_repository] = lambda: h.statements
    h.client.app.dependency_overrides[get_current_user] = _admin_claims
    assert h.settings.close_day == CLOSE_DAY, "test assumes the default close_day=20"
    return h


async def _new_account_with_card(h, *, issued_on: date):
    customer_id, paying_account_id = uuid.uuid4(), uuid.uuid4()
    h.card_accounts.known_customers.add(customer_id)
    h.card_accounts.known_accounts.add(paying_account_id)
    account = await h.card_accounts.create(
        customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=5000
    )
    backdated = dataclasses.replace(
        account, created_at=datetime.combine(issued_on, datetime.min.time(), tzinfo=timezone.utc)
    )
    h.card_accounts.rows[account.id] = backdated
    card = await h.cards.create(card_account_id=account.id, expiration_date=date.today() + timedelta(days=365 * 4))
    return backdated, card


def test_monthly_close_endpoint_closes_a_due_account_and_reports_it():
    import asyncio

    h = _harness()

    async def scenario():
        account, card = await _new_account_with_card(h, issued_on=date.today() - timedelta(days=40))
        return account, card

    account, card = asyncio.run(scenario())

    with h.client:
        response = h.client.post("/admin/batch/monthly-close")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["closed_count"] == 1
    assert len(body["statement_ids"]) == 1
    assert str(account.id) in body["card_account_ids"]
    # The real close logic actually ran — a statement row exists for real.
    assert any(row.card_account_id == account.id for row in h.statements.rows.values())


def test_monthly_close_endpoint_is_a_noop_when_nothing_is_due():
    import asyncio

    h = _harness()

    async def scenario():
        await _new_account_with_card(h, issued_on=date.today())

    asyncio.run(scenario())

    with h.client:
        response = h.client.post("/admin/batch/monthly-close")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["closed_count"] == 0
    assert body["statement_ids"] == []
    assert h.statements.rows == {}


def test_due_date_check_endpoint_finalizes_and_reports_a_late_fee():
    import asyncio

    h = _harness()
    today = date.today()

    async def scenario():
        account, card = await _new_account_with_card(h, issued_on=today - timedelta(days=60))
        now = datetime.now(timezone.utc)
        await h.card_movements.insert(CardMovement(
            id=uuid.uuid4(), card_id=card.id, request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("100.00"),
            currency="USD", created_at=now, occurred_at=now,
        ))
        # Close a statement whose due_date is today, with nothing paid —
        # `run_due_date_check` should finalize it and apply exactly one late fee.
        statement = await h.statements.create(
            account.id, today - timedelta(days=30), today - timedelta(days=1), today,
            purchases_total=Decimal("100.00"), interest_total=Decimal("0"),
            total_due=Decimal("100.00"), credit_balance=Decimal("0"),
            late_fees_total=Decimal("0"), minimum_payment=Decimal("10.00"),
        )
        return account, statement

    asyncio.run(scenario())

    with h.client:
        response = h.client.post("/admin/batch/due-date-check")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["finalized_count"] == 1
    assert body["late_fees_applied_count"] == 1
    late_fee_movements = [m for m in h.card_movements.rows if m.movement_type == CardMovementType.LATE_FEE]
    assert len(late_fee_movements) == 1


def test_due_date_check_endpoint_is_a_noop_when_nothing_is_due():
    h = _harness()
    with h.client as client:
        response = client.post("/admin/batch/due-date-check")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"finalized_count": 0, "late_fees_applied_count": 0}


def test_monthly_close_endpoint_rejects_a_caller_without_the_admin_permission():
    h = _harness()
    h.client.app.dependency_overrides[get_current_user] = _non_admin_claims

    with h.client as client:
        response = client.post("/admin/batch/monthly-close")

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "InsufficientPermissionsError"
    # Rejected before any batch logic ran — no statement was closed.
    assert h.statements.rows == {}


def test_due_date_check_endpoint_rejects_a_caller_without_the_admin_permission():
    h = _harness()
    h.client.app.dependency_overrides[get_current_user] = _non_admin_claims

    with h.client as client:
        response = client.post("/admin/batch/due-date-check")

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "InsufficientPermissionsError"


def test_monthly_close_endpoint_accepts_the_admin_permission_via_the_scope_fallback():
    # require_permissions falls back to a space-split `scope` string when
    # `permissions[]` is absent — proving `admin:batch` still works that way
    # too, not just via the primary `permissions[]` claim.
    h = _harness()
    h.client.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "auth0|admin-test", "scope": "admin:batch",
    }

    with h.client as client:
        response = client.post("/admin/batch/monthly-close")

    assert response.status_code == 200, response.text
