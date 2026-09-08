"""relax transactions for deposits: nullable counterparty, type deposit

Revision ID: 8f7e6d5c4b3a
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8f7e6d5c4b3a"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("transactions", "counterparty_account", existing_type=sa.String(16), nullable=True)
    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('debit', 'credit', 'declined', 'deposit')",
    )


def downgrade() -> None:
    # Remove deposit rows before re-adding NOT NULL (orphan guard)
    op.execute("DELETE FROM transactions WHERE type = 'deposit'")
    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('debit', 'credit', 'declined')",
    )
    op.alter_column("transactions", "counterparty_account", existing_type=sa.String(16), nullable=False)
