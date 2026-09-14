"""add transactions table

Revision ID: b3e7a9c1f4d0
Revises: a1c9f3d6e21b
Create Date: 2026-08-31 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'b3e7a9c1f4d0'
down_revision: Union[str, Sequence[str], None] = 'a1c9f3d6e21b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A pure read model, populated exclusively by TransactionConsumer off
    # `account-events` (spec §3.1). No CRUD route ever writes here.
    op.create_table(
        "transactions",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("account_number", sa.String(length=16), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("counterparty_account", sa.String(length=16), nullable=False),
        sa.Column("decline_reason", sa.String(length=50), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("type IN ('debit', 'credit', 'declined')", name="transactions_type_check"),
        sa.UniqueConstraint(
            "request_id", "account_number", "type", name="transactions_request_id_account_number_type_key"
        ),
    )
    op.create_index(
        "transactions_account_number_ts_id_idx",
        "transactions",
        ["account_number", sa.text("ts DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("transactions_account_number_ts_id_idx", table_name="transactions")
    op.drop_table("transactions")
