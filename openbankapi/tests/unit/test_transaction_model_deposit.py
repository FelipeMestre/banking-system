"""RED for Task 1.1 — transactions relax guard."""
from sqlalchemy import CheckConstraint

from openbankapi.infra.database.schemas.models import TransactionORM


def test_transaction_allows_deposit_type_and_nullable_counterparty():
    # counterparty must be nullable after relax
    assert TransactionORM.__table__.c.counterparty_account.nullable is True
    # type CHECK must include 'deposit'
    checks = [c for c in TransactionORM.__table_args__ if isinstance(c, CheckConstraint)]
    text = " ".join(str(c.sqltext) for c in checks)
    assert "deposit" in text


def test_transaction_model_still_allows_existing_types():
    from sqlalchemy import CheckConstraint

    checks = [c for c in TransactionORM.__table_args__ if isinstance(c, CheckConstraint)]
    text = " ".join(str(c.sqltext) for c in checks)
    for t in ("debit", "credit", "declined"):
        assert t in text
