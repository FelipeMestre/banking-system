"""RED/GREEN for task F2: `render` is pure formatting — feed real dataclass
instances, assert non-empty valid PDF bytes. No mocking needed."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from openbankapi.domain.model import (
    CardMovement,
    CardMovementType,
    Installment,
    InstallmentStatus,
    Statement,
    StatementStatus,
)
from openbankapi.infra.pdf.statement_pdf_generator import render


def _statement() -> Statement:
    now = datetime.now(timezone.utc)
    return Statement(
        id=uuid.uuid4(), card_account_id=uuid.uuid4(),
        period_start=date(2026, 8, 20), period_end=date(2026, 9, 20), due_date=date(2026, 10, 10),
        purchases_total=Decimal("950.00"), interest_total=Decimal("12.34"),
        total_due=Decimal("962.34"), paid_amount=Decimal("0.00"), credit_balance=Decimal("0.00"),
        late_fees_total=Decimal("0.00"), minimum_payment=Decimal("25.00"),
        paid_in_full=False, paid_by_due_date=False, status=StatementStatus.CLOSED,
        created_at=now, updated_at=now,
    )


def test_render_produces_nonempty_pdf_bytes():
    statement = _statement()
    now = datetime.now(timezone.utc)
    movements = [
        CardMovement(
            id=uuid.uuid4(), card_id=uuid.uuid4(), request_id=uuid.uuid4(),
            movement_type=CardMovementType.PURCHASE, amount=Decimal("850.00"),
            currency="USD", created_at=now,
        )
    ]
    installments = [
        Installment(
            id=uuid.uuid4(), card_movement_id=uuid.uuid4(), installment_number=1,
            amount=Decimal("100.00"), due_date=date(2026, 10, 20),
            status=InstallmentStatus.PENDING, created_at=now,
        )
    ]

    pdf_bytes = render(statement, movements, installments)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0


def test_render_with_no_movements_or_installments_still_produces_valid_pdf():
    pdf_bytes = render(_statement(), [], [])

    assert pdf_bytes.startswith(b"%PDF")
