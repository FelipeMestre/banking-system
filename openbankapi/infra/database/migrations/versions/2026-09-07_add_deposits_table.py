"""add deposits table

Revision ID: 9a8b7c6d5e4f
Revises: 8f7e6d5c4b3a
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, Sequence[str], None] = "8f7e6d5c4b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deposits",
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
        sa.UniqueConstraint("movement_id", name="deposits_movement_id_key"),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["transactions.id"], name="deposits_movement_id_fkey", ondelete="CASCADE"
        ),
    )
    op.create_index("deposits_movement_id_idx", "deposits", ["movement_id"])


def downgrade() -> None:
    op.drop_index("deposits_movement_id_idx", table_name="deposits")
    op.drop_table("deposits")
