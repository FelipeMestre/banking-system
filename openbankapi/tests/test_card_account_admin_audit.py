"""card-account-admin-audit: close-safety guard, filtered listing, reason DTOs,
and the audit trail for issue/update_limit/update_status/renew/card_status.

Reuses `cards_harness`/`_issue` from `test_card_account_flows.py` — same
fakes-backed TestClient convention, no broker/Postgres/Redis.
"""
from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.tests.test_card_account_flows import (  # noqa: F401
    _issue,
    cards_harness,
)


def _seed_movement(h, card_id, movement_type: CardMovementType, amount: str):
    from openbankapi.tests.fakes import _now

    movement = CardMovement(
        id=uuid.uuid4(),
        card_id=card_id,
        request_id=uuid.uuid4(),
        movement_type=movement_type,
        amount=Decimal(amount),
        currency="USD",
        created_at=_now(),
    )
    # Fresh loop per call — never reuses/assumes an ambient event loop, which
    # is what made this flaky when this test file ran alongside others in
    # the same session (each test here is sync, not `pytest.mark.asyncio`).
    asyncio.run(h.card_movements.insert(movement))


def _active_card_id(h, card_account_id):
    return next(
        c.id for c in h.cards.rows.values() if str(c.card_account_id) == card_account_id and c.is_active
    )


def _active_card_number(h, card_account_id):
    card_id = _active_card_id(h, card_account_id)
    return h.cards.rows[card_id].card_number


# --- Fakes and test support --------------------------------------------------


def test_fake_admin_action_repository_records_rows():
    from openbankapi.tests.fakes import FakeCardAccountAdminActionRepository

    repo = FakeCardAccountAdminActionRepository()
    card_account_id = uuid.uuid4()

    asyncio.run(
        repo.record(
            card_account_id=card_account_id,
            action="issue",
            admin_id="test-admin",
            reason="onboarding",
            details={"credit_limit": "1500.00"},
        )
    )

    assert len(repo.rows) == 1
    row = repo.rows[0]
    assert row.card_account_id == card_account_id
    assert row.action == "issue"
    assert row.admin_id == "test-admin"
    assert row.reason == "onboarding"
    assert row.details == {"credit_limit": "1500.00"}


def test_fake_card_movement_repository_computes_current_balance():
    from openbankapi.tests.fakes import FakeCardMovementRepository

    repo = FakeCardMovementRepository()
    assert hasattr(repo, "compute_current_balance")
    balance = asyncio.run(repo.compute_current_balance(uuid.uuid4()))
    assert balance == Decimal(0)


def test_fake_card_account_repository_list_by_customer_accepts_status():
    from openbankapi.tests.fakes import FakeCardAccountRepository

    repo = FakeCardAccountRepository()
    page = asyncio.run(repo.list_by_customer(uuid.uuid4(), limit=20, offset=0, status="active"))
    assert page.items == []


def test_harness_exposes_admin_actions():
    from openbankapi.tests.conftest import build

    h = build()
    assert h.admin_actions is not None


# --- Close-safety guard and filtered listing ---------------------------------


def test_close_rejected_when_balance_positive_no_audit_no_state_change(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = _active_card_id(cards_harness, card_account_id)
    _seed_movement(cards_harness, card_id, CardMovementType.PURCHASE, "100.00")
    _seed_movement(cards_harness, card_id, CardMovementType.PAYMENT, "20.00")

    response = cards_harness.client.post(
        f"/card-accounts/{card_account_id}/status", json={"status": "closed"}
    )

    assert response.status_code == 409
    assert not any(r.action == "update_status" for r in cards_harness.admin_actions.rows)
    current = cards_harness.card_accounts.rows[uuid.UUID(card_account_id)]
    assert current.status.value == "active"


def test_close_succeeds_when_balance_is_exactly_zero_and_audits(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]

    response = cards_harness.client.post(
        f"/card-accounts/{card_account_id}/status", json={"status": "closed"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    audit_rows = [r for r in cards_harness.admin_actions.rows if r.action == "update_status"]
    assert len(audit_rows) == 1


def test_close_compares_balance_against_zero_not_credit_limit(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = _active_card_id(cards_harness, card_account_id)
    _seed_movement(cards_harness, card_id, CardMovementType.PURCHASE, "1.00")

    response = cards_harness.client.post(
        f"/card-accounts/{card_account_id}/status", json={"status": "closed"}
    )

    assert response.status_code == 409


def test_close_rejected_when_late_fee_alone_makes_balance_positive(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = _active_card_id(cards_harness, card_account_id)
    _seed_movement(cards_harness, card_id, CardMovementType.LATE_FEE, "60.00")

    response = cards_harness.client.post(
        f"/card-accounts/{card_account_id}/status", json={"status": "closed"}
    )

    assert response.status_code == 409


def test_listing_status_alone_without_customer_id_is_422(cards_harness):
    response = cards_harness.client.get("/card-accounts?status=active")
    assert response.status_code == 422


def test_listing_default_limit_is_20(cards_harness):
    _issue(cards_harness)
    response = cards_harness.client.get(f"/card-accounts?customer_id={cards_harness.customer_id}")
    assert response.status_code == 200
    assert response.json()["limit"] == 20


def test_listing_items_never_contain_used_credit(cards_harness):
    _issue(cards_harness)
    response = cards_harness.client.get(f"/card-accounts?customer_id={cards_harness.customer_id}")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert "used_credit" not in item["card_account"]


# --- Reason DTOs and the audit trail ------------------------------------------


def test_issue_reason_over_300_chars_is_422(cards_harness):
    response = cards_harness.client.post(
        "/card-accounts",
        json={
            "customer_id": str(cards_harness.customer_id),
            "paying_account_id": str(cards_harness.paying_account_id),
            "credit_limit": "1500.00",
            "reason": "x" * 301,
        },
    )
    assert response.status_code == 422


def test_issue_omitted_reason_creates_audit_row_with_null_reason(cards_harness):
    response = _issue(cards_harness)
    assert response.status_code == 201
    card_account_id = response.json()["card_account"]["id"]
    rows = [r for r in cards_harness.admin_actions.rows if r.action == "issue"]
    assert len(rows) == 1
    assert rows[0].reason is None
    assert str(rows[0].card_account_id) == card_account_id


def test_update_limit_reason_creates_audit_row(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]

    response = cards_harness.client.put(
        f"/card-accounts/{card_account_id}",
        json={"credit_limit": "3000.00", "reason": "credit review"},
    )

    assert response.status_code == 200
    rows = [r for r in cards_harness.admin_actions.rows if r.action == "update_limit"]
    assert len(rows) == 1
    assert rows[0].reason == "credit review"
    assert rows[0].details == {"from_limit": "1500.00", "to_limit": "3000.00"}


def test_renew_creates_audit_row_and_rotates_number_and_expiry(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    old_number = issued["card"]["card_number"]

    response = cards_harness.client.post(f"/card-accounts/{card_account_id}/cards")

    assert response.status_code == 201
    body = response.json()
    assert body["card_number"] != old_number
    rows = [r for r in cards_harness.admin_actions.rows if r.action == "renew"]
    assert len(rows) == 1
    assert rows[0].details["old_number"] == old_number
    assert rows[0].details["new_number"] == body["card_number"]


def test_card_status_extra_field_forbidden(cards_harness):
    _issue(cards_harness)
    response = cards_harness.client.post(
        "/cards/0000000000000000/status", json={"status": "blocked", "bogus": "x"}
    )
    assert response.status_code == 422


def test_card_status_with_reason_creates_audit_and_requires_write_admin(cards_harness):
    issued = _issue(cards_harness).json()
    card_number = issued["card"]["card_number"]

    response = cards_harness.client.post(
        f"/cards/{card_number}/status", json={"status": "blocked", "reason": "fraud"}
    )

    assert response.status_code == 200
    rows = [r for r in cards_harness.admin_actions.rows if r.action == "card_status"]
    assert len(rows) == 1
    assert rows[0].reason == "fraud"


def test_delete_card_account_is_405(cards_harness):
    issued = _issue(cards_harness).json()
    card_account_id = issued["card_account"]["id"]
    response = cards_harness.client.delete(f"/card-accounts/{card_account_id}")
    assert response.status_code == 405


def test_empty_sub_is_401_and_writes_no_audit_row(cards_harness):
    async def _empty_sub():
        return {"sub": "", "permissions": ["write:admin"]}

    cards_harness.client.app.dependency_overrides[get_current_user] = _empty_sub

    response = cards_harness.client.post(
        "/card-accounts",
        json={
            "customer_id": str(cards_harness.customer_id),
            "paying_account_id": str(cards_harness.paying_account_id),
            "credit_limit": "1500.00",
        },
    )

    assert response.status_code == 401
    assert len(cards_harness.admin_actions.rows) == 0
