"""RED/GREEN for task B1: `Statement` domain dataclass — no DB dependency."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from openbankapi.domain.model import Statement, StatementStatus


def test_statement_constructs_and_exposes_all_fields():
    card_account_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    statement = Statement(
        id=uuid.uuid4(),
        card_account_id=card_account_id,
        period_start=date(2026, 8, 20),
        period_end=date(2026, 9, 20),
        due_date=date(2026, 10, 10),
        purchases_total=Decimal("950.00"),
        interest_total=Decimal("12.34"),
        total_due=Decimal("962.34"),
        paid_amount=Decimal("0.00"),
        credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"),
        minimum_payment=Decimal("25.00"),
        paid_in_full=False,
        paid_by_due_date=False,
        status=StatementStatus.OPEN,
        created_at=now,
        updated_at=now,
    )

    assert statement.card_account_id == card_account_id
    assert statement.purchases_total == Decimal("950.00")
    assert statement.total_due == Decimal("962.34")
    assert statement.status is StatementStatus.OPEN
    assert statement.paid_in_full is False
