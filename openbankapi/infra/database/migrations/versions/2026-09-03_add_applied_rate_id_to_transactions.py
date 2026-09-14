"""add applied_rate_id to transactions

Revision ID: d4f6b2a90c58
Revises: c92d5e8a17f3
Create Date: 2026-09-03 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'd4f6b2a90c58'
down_revision: Union[str, Sequence[str], None] = 'c92d5e8a17f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable and additive (FX-16): a transaction row settled before this
    # phase, or one for a same-currency transfer, links to no applied-rate
    # audit row at all.
    op.add_column(
        "transactions",
        sa.Column(
            "applied_rate_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("applied_rates.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "applied_rate_id")
