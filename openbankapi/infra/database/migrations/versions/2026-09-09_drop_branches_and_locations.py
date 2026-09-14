"""drop branches and locations tables and accounts.branch_id

Revision ID: afbd19e21814
Revises: e7f8a9b0c1d2
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "afbd19e21814"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop in FK-dependency order: accounts -> branches -> locations.
    op.drop_constraint("accounts_branch_id_fkey", "accounts", type_="foreignkey")
    op.drop_column("accounts", "branch_id")
    op.drop_table("branches")  # drops branches_location_id_fkey, branches_code_key with it
    op.drop_table("locations")


def downgrade() -> None:
    # Nullable-on-downgrade asymmetry, documented: a real DROP COLUMN destroys
    # data, so there is nothing to backfill a NOT NULL `accounts.branch_id`
    # with for existing rows. Recreating it nullable is the only truthful
    # reversible shape — the original baseline had it NOT NULL.
    op.create_table(
        "locations",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "branches",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "location_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("locations.id"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="branches_code_key"),
    )
    op.add_column(
        "accounts",
        sa.Column("branch_id", PgUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "accounts_branch_id_fkey", "accounts", "branches", ["branch_id"], ["id"]
    )
