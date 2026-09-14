"""add withdrawals table and widen transactions type check

Revision ID: e7f8a9b0c1d2
Revises: c48a3cea9507
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "c48a3cea9507"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "withdrawals",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "movement_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("admin_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("movement_id", name="withdrawals_movement_id_key"),
        sa.ForeignKeyConstraint(
            ["movement_id"],
            ["transactions.id"],
            name="withdrawals_movement_id_fkey",
            ondelete="CASCADE",
        ),
    )
    op.create_index("withdrawals_movement_id_idx", "withdrawals", ["movement_id"])

    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('debit', 'credit', 'declined', 'deposit', 'withdrawal')",
    )


def downgrade() -> None:
    # Remove withdrawal rows before narrowing the check constraint (orphan guard)
    op.execute("DELETE FROM transactions WHERE type = 'withdrawal'")
    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('debit', 'credit', 'declined', 'deposit')",
    )

    op.drop_index("withdrawals_movement_id_idx", table_name="withdrawals")
    op.drop_table("withdrawals")
