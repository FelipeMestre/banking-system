"""add card account admin actions audit table

Revision ID: d4e5f6a7b8c9
Revises: 8f7e6d5c4b3a
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "8f7e6d5c4b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_account_admin_actions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "card_account_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("admin_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('issue','update_limit','update_status','card_status','renew')",
            name="card_account_admin_actions_action_check",
        ),
        sa.ForeignKeyConstraint(
            ["card_account_id"],
            ["card_accounts.id"],
            name="card_account_admin_actions_card_account_id_fkey",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "card_account_admin_actions_card_account_id_created_at_id_idx",
        "card_account_admin_actions",
        ["card_account_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "card_account_admin_actions_admin_id_idx",
        "card_account_admin_actions",
        ["admin_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "card_account_admin_actions_admin_id_idx",
        table_name="card_account_admin_actions",
    )
    op.drop_index(
        "card_account_admin_actions_card_account_id_created_at_id_idx",
        table_name="card_account_admin_actions",
    )
    op.drop_table("card_account_admin_actions")
