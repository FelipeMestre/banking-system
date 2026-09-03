"""add applied_rates table

Revision ID: a618b754f8ac
Revises: a1c9f3d6e21b
Create Date: 2026-09-02 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'a618b754f8ac'
down_revision: Union[str, Sequence[str], None] = 'a1c9f3d6e21b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Passive audit table for FX-14: built and migrated in this phase, but
    # nothing writes to it yet — no route in this phase calls
    # IAppliedRateRepository.insert() (FX-13/FX-15 scope guard).
    op.create_table(
        "applied_rates",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pair", sa.String(length=7), nullable=False),
        sa.Column("mid_rate", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("applied_rate", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("margin", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("source_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "direction IN ('credit', 'debit')", name="applied_rates_direction_check"
        ),
    )


def downgrade() -> None:
    op.drop_table("applied_rates")
