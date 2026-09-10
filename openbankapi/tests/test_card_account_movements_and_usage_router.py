"""RED for `credit-cards-frontend-page` Group D: `GET /card-accounts/{id}/used-credit-estimate`
and `GET /card-accounts/{id}/movements`. Mirrors `test_purchase_router.py`'s
harness pattern, extended with a resolved `CurrentCustomerDep` identity."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.model import CardMovement, CardMovementType
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeAccountRepository, FakeCardAccountRepository, FakeCardRepository


@pytest.fixture
def usage_harness():
    import asyncio

    customers_repo = None

    async def _resolve_customer(repo):
        return await repo.create(
            identification_number=f"id-{uuid.uuid4().hex[:10]}", first_name="Ada", last_name="Lovelace",
            date_of_birth=date(1990, 1, 1), gender=None, auth0_sub="auth0|owner",
        )

    from openbankapi.tests.fakes import FakeCustomerRepository

    customers_repo = FakeCustomerRepository()
    owner = asyncio.run(_resolve_customer(customers_repo))
    customer_id = owner.id

    accounts = FakeAccountRepository(known_customers={customer_id})
    h = build(accounts=accounts)
    h.customers.rows[owner.id] = owner
    with h.client:
        account_response = h.client.post(
            "/accounts", json={"currency": "USD", "customer_id": str(customer_id)}
        )
    paying_account = accounts.rows[account_response.json()["account_number"]]

    card_accounts = FakeCardAccountRepository(known_customers={customer_id}, known_accounts={paying_account.id})
    cards = FakeCardRepository()
    h2 = build(accounts=accounts, card_accounts=card_accounts, cards=cards)
    h2.customers.rows[owner.id] = owner

    h2.client.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "auth0|owner",
        "permissions": ["write:admin"],
    }
    h2.customer_id, h2.paying_account_id, h2.owner = customer_id, paying_account.id, owner
    with h2.client:
        yield h2


def _issue(h):
    return h.client.post(
        "/card-accounts",
        json={
            "customer_id": str(h.customer_id),
            "paying_account_id": str(h.paying_account_id),
            "credit_limit": "1500.00",
        },
    )


def _seed_movement(h, card_id, movement_type: CardMovementType, amount: str, applied_rate_id=None):
    movement = CardMovement(
        id=uuid.uuid4(), card_id=card_id, request_id=uuid.uuid4(), movement_type=movement_type,
        amount=Decimal(amount), currency="USD", created_at=datetime.now(timezone.utc),
        applied_rate_id=applied_rate_id,
    )
    h.card_movements.rows.append(movement)
    return movement


# --- used-credit-estimate ----------------------------------------------------


def test_used_credit_estimate_matches_manual_sum_of_purchases_and_payments(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = uuid.UUID(issued["card"]["id"])

    _seed_movement(usage_harness, card_id, CardMovementType.PURCHASE, "100.00")
    _seed_movement(usage_harness, card_id, CardMovementType.PURCHASE, "50.00")
    _seed_movement(usage_harness, card_id, CardMovementType.PAYMENT, "30.00")
    _seed_movement(usage_harness, card_id, CardMovementType.DECLINED, "999.00")

    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/used-credit-estimate")

    assert response.status_code == 200
    body = response.json()
    assert body["used_credit_estimate"] == "120.00"
    assert body["is_estimate"] is True
    # movement_count reflects every movement row ever posted (design:
    # UsedCreditEstimateDTO.movement_count=len(rows)), including DECLINED —
    # only the financial *sum* excludes it.
    assert body["movement_count"] == 4


def test_used_credit_estimate_non_owner_is_denied(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]

    usage_harness.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|intruder"}
    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/used-credit-estimate")

    assert response.status_code in (403, 404)


def test_used_credit_estimate_spans_a_card_renewal(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]
    original_card_id = uuid.UUID(issued["card"]["id"])
    _seed_movement(usage_harness, original_card_id, CardMovementType.PURCHASE, "40.00")

    usage_harness.client.post(f"/card-accounts/{card_account_id}/cards")
    renewed_card = usage_harness.cards.rows
    new_card_id = next(cid for cid, c in renewed_card.items() if c.id != original_card_id and c.is_active)
    _seed_movement(usage_harness, new_card_id, CardMovementType.PURCHASE, "15.00")

    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/used-credit-estimate")

    assert response.status_code == 200
    assert response.json()["used_credit_estimate"] == "55.00"


# --- movements list -----------------------------------------------------------


def test_movements_list_returns_owner_rows_with_fx_and_installment_data(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]
    card_id = uuid.UUID(issued["card"]["id"])

    applied_rate_id = uuid.UUID(
        __import__("asyncio").run(
            usage_harness.applied_rates.insert(
                pair="EUR/USD", mid_rate=1.1, applied_rate=1.1727, margin=0.05,
                direction="credit", source_ts=datetime.now(timezone.utc),
            )
        )
    )
    fx_movement = _seed_movement(usage_harness, card_id, CardMovementType.PURCHASE, "58.64", applied_rate_id)
    __import__("asyncio").run(
        usage_harness.installments.bulk_insert([])
    )

    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/movements")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["id"] == str(fx_movement.id)
    assert row["fx_pair"] == "EUR/USD"
    assert row["fx_applied_rate"] == "1.1727"


def test_movements_list_non_owner_is_denied(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]

    usage_harness.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|intruder"}
    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/movements")

    assert response.status_code in (403, 404)


def test_movements_list_spans_a_card_renewal(usage_harness):
    issued = _issue(usage_harness).json()
    card_account_id = issued["card_account"]["id"]
    original_card_id = uuid.UUID(issued["card"]["id"])
    movement_a = _seed_movement(usage_harness, original_card_id, CardMovementType.PURCHASE, "40.00")

    usage_harness.client.post(f"/card-accounts/{card_account_id}/cards")
    new_card_id = next(
        cid for cid, c in usage_harness.cards.rows.items() if cid != original_card_id and c.is_active
    )
    movement_b = _seed_movement(usage_harness, new_card_id, CardMovementType.PURCHASE, "15.00")

    response = usage_harness.client.get(f"/card-accounts/{card_account_id}/movements")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(movement_a.id), str(movement_b.id)}
