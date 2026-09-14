"""add statement totals columns

Revision ID: a1b2c3d4e5f6
Revises: f3c8d1a5e9b7
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f3c8d1a5e9b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Additive only: `closing_balance`/`status` are left untouched (design's
# explicit decision — no repurposing, no rename, no destructive migration).
_NUMERIC_COLUMNS = (
    "purchases_total",
    "interest_total",
    "total_due",
    "paid_amount",
    "credit_balance",
    "late_fees_total",
)
_BOOLEAN_COLUMNS = ("paid_in_full", "paid_by_due_date")


def upgrade() -> None:
    for name in _NUMERIC_COLUMNS:
        op.add_column(
            "statements",
            sa.Column(name, sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        )
    for name in _BOOLEAN_COLUMNS:
        op.add_column(
            "statements",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    for name in _BOOLEAN_COLUMNS:
        op.drop_column("statements", name)
    for name in _NUMERIC_COLUMNS:
        op.drop_column("statements", name)
