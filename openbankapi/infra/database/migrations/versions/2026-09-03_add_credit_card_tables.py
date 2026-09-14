"""add credit card tables

Revision ID: e7a1c4f9b2d6
Revises: d4f6b2a90c58
Create Date: 2026-09-03 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'e7a1c4f9b2d6'
down_revision: Union[str, Sequence[str], None] = 'd4f6b2a90c58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_accounts",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("customer_id", PgUUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("paying_account_id", PgUUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("credit_limit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('active','blocked','closed')", name="card_accounts_status_check"
        ),
    )

    op.create_table(
        "cards",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_account_id", PgUUID(as_uuid=True), sa.ForeignKey("card_accounts.id"), nullable=False),
        sa.Column("card_number", sa.CHAR(length=16), nullable=False, unique=True),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(r"card_number ~ '^[0-9]{16}$'", name="cards_card_number_check"),
        sa.CheckConstraint(
            "status IN ('active','blocked','replaced','expired')", name="cards_status_check"
        ),
    )

    op.create_table(
        "statements",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_account_id", PgUUID(as_uuid=True), sa.ForeignKey("card_accounts.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("closing_balance", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("minimum_payment", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('open','closed','paid','overdue')", name="statements_status_check"
        ),
    )

    op.create_table(
        "card_movements",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_id", PgUUID(as_uuid=True), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("applied_rate_id", PgUUID(as_uuid=True), sa.ForeignKey("applied_rates.id"), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("movement_type", sa.String(length=20), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "movement_type IS NULL OR movement_type IN "
            "('purchase','payment','fee','interest','refund')",
            name="card_movements_movement_type_check",
        ),
    )

    op.create_table(
        "installments",
        sa.Column(
            "id", PgUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_movement_id", PgUUID(as_uuid=True), sa.ForeignKey("card_movements.id"), nullable=False),
        sa.Column("installment_number", sa.SmallInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IS NULL OR status IN ('pending','paid','overdue')",
            name="installments_status_check",
        ),
    )


def downgrade() -> None:
    # FK-dependency order: installments -> card_movements -> statements -> cards -> card_accounts.
    op.drop_table("installments")
    op.drop_table("card_movements")
    op.drop_table("statements")
    op.drop_table("cards")
    op.drop_table("card_accounts")
