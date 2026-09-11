"""RED/GREEN for `credit-card-monthly-batch-statements`'s new customer-facing
endpoints: `GET /card-accounts/{id}/statements`,
`GET /card-accounts/{id}/statements/{statement_id}/pdf`,
`GET /card-accounts/{id}/installment-payoff`, and the `statement_id` filter on
the existing `GET /card-accounts/{id}/movements`. Mirrors
`test_card_account_movements_and_usage_router.py`'s harness pattern exactly.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from openbankapi.config.dependencies import get_current_user
from openbankapi.domain.model import CardMovement, CardMovementType, Installment, InstallmentStatus
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import (
    FakeAccountRepository,
    FakeCardAccountRepository,
    FakeCardRepository,
    FakeCustomerRepository,
)


@pytest.fixture
def statement_harness():
    async def _resolve_customer(repo):
        return await repo.create(
            identification_number=f"id-{uuid.uuid4().hex[:10]}", first_name="Ada", last_name="Lovelace",
            date_of_birth=date(1990, 1, 1), gender=None, auth0_sub="auth0|owner",
        )

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


def _seed_statement(h, card_account_id, *, period_start, period_end, due_date, **overrides):
    kwargs = dict(
        purchases_total=Decimal("100.00"), interest_total=Decimal("0.00"),
        total_due=Decimal("100.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("10.00"),
    )
    kwargs.update(overrides)
    return asyncio.run(
        h.statements.create(card_account_id, period_start, period_end, due_date, **kwargs)
    )


def _seed_movement(h, card_id, movement_type: CardMovementType, amount: str, occurred_at=None):
    movement = CardMovement(
        id=uuid.uuid4(), card_id=card_id, request_id=uuid.uuid4(), movement_type=movement_type,
        amount=Decimal(amount), currency="USD",
        created_at=occurred_at or datetime.now(timezone.utc), occurred_at=occurred_at,
    )
    h.card_movements.rows.append(movement)
    return movement


# --- statements list ----------------------------------------------------------


def test_list_statements_returns_newest_first_scoped_to_owner(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    older = _seed_statement(
        h, card_account_id, period_start=date(2026, 6, 20), period_end=date(2026, 7, 20),
        due_date=date(2026, 8, 10),
    )
    newer = _seed_statement(
        h, card_account_id, period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 10),
    )
    # a statement on a DIFFERENT account must never leak into this list
    _seed_statement(
        h, uuid.uuid4(), period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 10),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/statements")

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [str(newer.id), str(older.id)]


def test_list_statements_non_owner_is_denied(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = issued["card_account"]["id"]

    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|intruder"}
    response = h.client.get(f"/card-accounts/{card_account_id}/statements")

    assert response.status_code in (403, 404)


# --- installment payoff --------------------------------------------------------


def test_installment_payoff_sums_unbilled_installments(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    card_id = uuid.UUID(issued["card"]["id"])

    plan_purchase = _seed_movement(h, card_id, CardMovementType.PURCHASE, "300.00")
    now = datetime.now(timezone.utc)
    asyncio.run(
        h.installments.bulk_insert(
            [
                Installment(
                    id=uuid.uuid4(), card_movement_id=plan_purchase.id, installment_number=i + 1,
                    amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
                    created_at=now,
                )
                for i in range(3)
            ]
        )
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/installment-payoff")

    assert response.status_code == 200
    body = response.json()
    assert body["payoff_amount"] == "300.00"
    assert body["card_account_id"] == str(card_account_id)


# --- statement PDF download -----------------------------------------------------


def test_download_statement_pdf_returns_real_pdf_bytes(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    statement = _seed_statement(
        h, card_account_id, period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 10),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/statements/{statement.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 0


def test_download_statement_pdf_wrong_account_is_not_found(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    other_account_statement = _seed_statement(
        h, uuid.uuid4(), period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 10),
    )

    response = h.client.get(
        f"/card-accounts/{card_account_id}/statements/{other_account_statement.id}/pdf"
    )

    assert response.status_code == 404


def test_download_statement_pdf_non_owner_is_denied(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    statement = _seed_statement(
        h, card_account_id, period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 10),
    )

    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|intruder"}
    response = h.client.get(f"/card-accounts/{card_account_id}/statements/{statement.id}/pdf")

    assert response.status_code in (403, 404)


# --- movements scoped to one cycle ----------------------------------------------


def test_movements_filtered_by_statement_id_merges_period_and_billed_installment(statement_harness):
    """A single-charge purchase inside the period is included by date. An
    installment plan purchase made LONG BEFORE this period must still show
    up for this cycle if (and only if) this exact statement billed one of
    its installments — proving the merge is by `mark_billed` assignment, not
    by re-checking the parent purchase's original date."""
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    card_id = uuid.UUID(issued["card"]["id"])

    period_start, period_end = date(2026, 7, 20), date(2026, 8, 20)
    statement = _seed_statement(
        h, card_account_id, period_start=period_start, period_end=period_end,
        due_date=date(2026, 9, 10),
    )

    in_period_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    single_charge = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "75.00", occurred_at=in_period_dt
    )
    outside_period = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "999.00",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    long_ago_plan_purchase = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "900.00",
        occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    now = datetime.now(timezone.utc)
    installments = [
        Installment(
            id=uuid.uuid4(), card_movement_id=long_ago_plan_purchase.id, installment_number=i + 1,
            amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
            created_at=now,
        )
        for i in range(9)
    ]
    asyncio.run(h.installments.bulk_insert(installments))
    asyncio.run(h.installments.mark_billed(installments[0].id, statement.id))

    response = h.client.get(
        f"/card-accounts/{card_account_id}/movements", params={"statement_id": str(statement.id)}
    )

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}

    assert str(single_charge.id) == list(ids & {str(single_charge.id)})[0]
    assert str(outside_period.id) not in ids
    # the long-ago plan purchase's OWN movement row is excluded...
    assert str(long_ago_plan_purchase.id) not in ids
    # ...replaced by a row representing the ONE installment this statement billed
    assert str(installments[0].id) in ids
    billed_row = next(item for item in body["items"] if item["id"] == str(installments[0].id))
    assert billed_row["amount"] == "100.00"
    assert billed_row["installment_count"] == 9


def test_movements_filtered_by_unknown_statement_id_is_not_found(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    response = h.client.get(
        f"/card-accounts/{card_account_id}/movements", params={"statement_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


# --- movements scoped to the open cycle via `since` ------------------------------


def test_movements_since_returns_movement_after_latest_statement_period_end(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    card_id = uuid.UUID(issued["card"]["id"])

    _seed_statement(
        h, card_account_id, period_start=date(2026, 7, 21), period_end=date(2026, 8, 20),
        due_date=date(2026, 9, 9),
    )
    open_cycle_purchase = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "42.00",
        occurred_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
    before_since = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "999.00",
        occurred_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )

    response = h.client.get(
        f"/card-accounts/{card_account_id}/movements", params={"since": "2026-08-21"}
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(open_cycle_purchase.id) in ids
    assert str(before_since.id) not in ids


def test_movements_since_excludes_installment_plan_parent(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    card_id = uuid.UUID(issued["card"]["id"])

    plan_purchase = _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "900.00",
        occurred_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
    now = datetime.now(timezone.utc)
    asyncio.run(h.installments.bulk_insert([
        Installment(
            id=uuid.uuid4(), card_movement_id=plan_purchase.id, installment_number=i + 1,
            amount=Decimal("100.00"), due_date=date.today(), status=InstallmentStatus.PENDING,
            created_at=now,
        )
        for i in range(9)
    ]))

    response = h.client.get(
        f"/card-accounts/{card_account_id}/movements", params={"since": "2026-08-01"}
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(plan_purchase.id) not in ids


def test_movements_statement_id_and_since_together_is_422(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    response = h.client.get(
        f"/card-accounts/{card_account_id}/movements",
        params={"statement_id": str(uuid.uuid4()), "since": "2026-08-01"},
    )

    assert response.status_code == 422


# --- current-cycle projection -----------------------------------------------------


def test_current_cycle_happy_path_shape(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])
    card_id = uuid.UUID(issued["card"]["id"])
    # Seed a closed, not-yet-due, fully-paid previous statement so
    # `period_start` is a deterministic date rather than depending on the
    # card account's real issuance timestamp (avoids UTC/local midnight
    # boundary flakiness in `date.today()` comparisons).
    previous = _seed_statement(
        h, card_account_id,
        period_start=date.today() - timedelta(days=30), period_end=date.today() - timedelta(days=1),
        due_date=date.today() + timedelta(days=20), total_due=Decimal("100.00"),
    )
    asyncio.run(h.statements.finalize_due_date_outcome(
        previous.id, paid_amount=Decimal("100.00"), paid_in_full=True, paid_by_due_date=True
    ))
    _seed_movement(
        h, card_id, CardMovementType.PURCHASE, "60.00",
        occurred_at=datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc).replace(hour=12),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/current-cycle")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "period_start", "projected_period_end", "overdue_from_previous_cycle",
        "interest_on_overdue", "new_purchases_this_cycle", "total_to_pay", "payable",
    }
    assert body["overdue_from_previous_cycle"] is None
    assert body["interest_on_overdue"] is None
    assert body["new_purchases_this_cycle"] == "60.00"
    assert body["total_to_pay"] == "60.00"
    assert body["payable"] is True


def test_current_cycle_overdue_absent_when_due_date_not_yet_passed(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    future_due_date = date.today() + timedelta(days=5)
    _seed_statement(
        h, card_account_id,
        period_start=date.today() - timedelta(days=30), period_end=date.today() - timedelta(days=1),
        due_date=future_due_date, total_due=Decimal("500.00"),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/current-cycle")

    assert response.status_code == 200
    body = response.json()
    assert body["overdue_from_previous_cycle"] is None
    assert body["interest_on_overdue"] is None


def test_current_cycle_non_owner_is_denied(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = issued["card_account"]["id"]

    h.client.app.dependency_overrides[get_current_user] = lambda: {"sub": "auth0|intruder"}
    response = h.client.get(f"/card-accounts/{card_account_id}/current-cycle")

    assert response.status_code in (403, 404)


# --- statement payable field --------------------------------------------------------


def test_only_latest_closed_statement_is_payable_while_due_date_not_passed(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    older = _seed_statement(
        h, card_account_id, period_start=date(2026, 6, 20), period_end=date(2026, 7, 20),
        due_date=date.today() + timedelta(days=30),
    )
    newer = _seed_statement(
        h, card_account_id, period_start=date(2026, 7, 20), period_end=date(2026, 8, 20),
        due_date=date.today() + timedelta(days=10),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/statements")

    assert response.status_code == 200
    by_id = {row["id"]: row for row in response.json()}
    assert by_id[str(newer.id)]["payable"] is True
    assert by_id[str(older.id)]["payable"] is False


def test_latest_closed_statement_not_payable_once_due_date_passed(statement_harness):
    h = statement_harness
    issued = _issue(h).json()
    card_account_id = uuid.UUID(issued["card_account"]["id"])

    latest = _seed_statement(
        h, card_account_id, period_start=date(2026, 6, 20), period_end=date(2026, 7, 20),
        due_date=date.today() - timedelta(days=1),
    )

    response = h.client.get(f"/card-accounts/{card_account_id}/statements")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(latest.id)
    assert body[0]["payable"] is False
